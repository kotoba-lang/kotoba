/* aiueos AArch64 kernel spike (ADR-2608080600 track a2).
 *
 * Validates the boot-info handoff, replaces the firmware's page tables with
 * its own TTBR0_EL1 four-level-capable map, and proves W^X is actually
 * enforced by deliberately violating it in both directions.
 *
 * This is the AArch64 counterpart of the x86_64 Phase-1/2 evidence in
 * os/aiueos/README.md: "the kernel replaces the firmware CR3 with its own
 * four-level identity map, enables write-protect and NX, and maps text RX,
 * rodata R+NX, and writable state RW+NX. [...] The smoke test writes to text
 * and attempts to execute a byte in rodata; both must raise vector 14 with the
 * expected x86 page fault error-code bits before execution can continue."
 *
 * The AArch64 mechanism differs completely (TTBR0/TCR/MAIR/SCTLR instead of
 * CR3/CR0/EFER, ESR_EL1 instead of an error code, no port I/O) while the
 * decision the evidence encodes is identical.
 */
#include <stdint.h>
#include "bootinfo.h"

/* --------------------------------------------------------------------------
 * PL011 serial. AArch64 has no port I/O, so every marker goes out over MMIO.
 */
#define PL011_DR ((volatile uint32_t *)(PL011_BASE + 0x00))
#define PL011_FR ((volatile uint32_t *)(PL011_BASE + 0x18))
#define PL011_FR_TXFF (1u << 5)

static void serial_putc(char c) {
  while (*PL011_FR & PL011_FR_TXFF) { }
  *PL011_DR = (uint32_t)(unsigned char)c;
}
static void serial_puts(const char *s) {
  for (; *s; s++) { if (*s == '\n') serial_putc('\r'); serial_putc(*s); }
}
static void serial_puthex(uint64_t v) {
  serial_puts("0x");
  for (int shift = 60; shift >= 0; shift -= 4)
    serial_putc("0123456789abcdef"[(v >> shift) & 0xf]);
}
static void serial_putdec(uint64_t v) {
  char buf[21]; int i = 0;
  if (!v) { serial_putc('0'); return; }
  while (v) { buf[i++] = (char)('0' + v % 10); v /= 10; }
  while (i--) serial_putc(buf[i]);
}

/* --------------------------------------------------------------------------
 * Linker-provided section bounds. These are what let each region get distinct
 * permissions; without the 4 KiB alignment in kernel.ld the W^X split would
 * not be expressible at page granularity.
 */
extern char __text_start[], __text_end[];
extern char __rodata_start[], __rodata_end[];
extern char __end[];

/* --------------------------------------------------------------------------
 * UEFI memory map, as handed over in boot-info. Descriptors are strided by the
 * firmware's `descriptor_size`, which is NOT sizeof(struct) — walking with the
 * struct size is the classic way to read a corrupt map.
 */
struct efi_memory_descriptor {
  uint32_t type;
  uint32_t pad;
  uint64_t physical_start;
  uint64_t virtual_start;
  uint64_t number_of_pages;
  uint64_t attribute;
};
#define EFI_CONVENTIONAL_MEMORY 7

struct reserved_range { uint64_t base, size; };

/* --------------------------------------------------------------------------
 * THE DECISION.
 *
 * ADR-2607241100 D6 draws the line: C owns mechanism, every judgement is a
 * compiler-emitted Kotoba object. This function is a judgement — which physical
 * memory may be handed out — and so belongs in Kotoba, not here.
 *
 * It is not in Kotoba today because there is no way to put it there on AArch64.
 * `kotoba.native.elf64/package-kernel-object` emits "a linkable x86-64 ET_REL
 * object" and hard-rejects any target other than `:x86_64-aiueos-kernel-v1`;
 * the aarch64 target only reaches `package-kernel-aarch64`, which emits a whole
 * standalone ET_EXEC image. There is no aarch64 ET_REL emitter, so a Kotoba
 * decision object cannot be linked into a C-mechanism kernel at all.
 *
 * So it is written here as a PURE function of (descriptor, reserved ranges) ->
 * admitted sub-range, touching no global state and doing no I/O, precisely so
 * it is a drop-in replacement once that emitter exists. Keep it that way: the
 * moment it reads a global or allocates, the swap stops being mechanical.
 */
static int page_range_admissible(const struct efi_memory_descriptor *d,
                                 const struct reserved_range *reserved, int reserved_count,
                                 uint64_t *out_base, uint64_t *out_pages) {
#ifdef AIUEOS_BREAK_PMM
  /* Negative control for the gate (never a build option for real use): a
     judgement that trusts the firmware map. It drops BOTH the type filter and
     the reserved-range exclusion below, so the allocator may hand out the
     kernel image, the boot-info page or the memory map itself.
     Dropping only the reserved-range exclusion is NOT a usable control: under
     AAVMF every reserved range is EfiLoaderData, so the type filter alone
     already excludes them and the control comes out byte-identical to a
     correct build. Measured 2026-08-08 — the first attempt at this control was
     vacuous for exactly that reason. */
  if (d->type != EFI_CONVENTIONAL_MEMORY && d->type != 2 /* EfiLoaderData */) return 0;
#else
  if (d->type != EFI_CONVENTIONAL_MEMORY) return 0;
#endif
  if (d->number_of_pages == 0) return 0;
  if (d->physical_start & 0xFFFULL) return 0;           /* must be page aligned */

  uint64_t base = d->physical_start;
  uint64_t end = base + d->number_of_pages * 4096ULL;
  if (end <= base) return 0;                            /* overflow */

  /* Trim against every reserved range. A descriptor that a reserved range cuts
     in half is refused outright rather than split — refusing is safe, and
     splitting would need an allocator policy this judgement must not own. */
#ifdef AIUEOS_BREAK_PMM
  /* Negative control for the gate (never a build option for real use): skip the
     reserved-range exclusion entirely, so the allocator may hand out the kernel
     image, the boot-info page or the memory map. A gate that actually checks
     the judgement must reject this build. */
  (void)reserved; (void)reserved_count;
  goto skip_reserved;
#endif
  for (int i = 0; i < reserved_count; i++) {
    uint64_t r0 = reserved[i].base;
    uint64_t r1 = reserved[i].base + reserved[i].size;
    if (r1 <= base || r0 >= end) continue;              /* disjoint */
    if (r0 <= base && r1 >= end) return 0;              /* fully covered */
    if (r0 <= base) { base = r1; continue; }            /* overlaps the front */
    if (r1 >= end) { end = r0; continue; }              /* overlaps the tail */
    return 0;                                           /* splits it: refuse */
  }
#ifdef AIUEOS_BREAK_PMM
skip_reserved:
#endif

  base = (base + 0xFFFULL) & ~0xFFFULL;
  end &= ~0xFFFULL;
  if (end <= base) return 0;

  *out_base = base;
  *out_pages = (end - base) / 4096ULL;
  return 1;
}

/* --------------------------------------------------------------------------
 * Physical page allocator. Mechanism only: it hands out pages from the ranges
 * the judgement above admitted, and never decides what is admissible.
 */
#define PMM_MAX_REGIONS 64

struct pmm {
  struct { uint64_t base, pages; } region[PMM_MAX_REGIONS];
  int region_count;
  uint64_t total_pages;
  uint64_t allocated;
  int cursor_region;
  uint64_t cursor_page;
  uint64_t limit;              /* 0 = unlimited; a test-only cap */
  int truncated;               /* map had more admissible regions than we hold */
};
static struct pmm pmm;

static void pmm_init(const struct aiueos_boot_info *info,
                     const struct reserved_range *reserved, int reserved_count) {
  pmm.region_count = 0; pmm.total_pages = 0; pmm.allocated = 0;
  pmm.cursor_region = 0; pmm.cursor_page = 0; pmm.limit = 0; pmm.truncated = 0;

  const unsigned char *p = (const unsigned char *)info->memory_map;
  uint64_t stride = info->descriptor_size;
  uint64_t count = stride ? info->memory_map_size / stride : 0;

  for (uint64_t i = 0; i < count; i++) {
    const struct efi_memory_descriptor *d =
      (const struct efi_memory_descriptor *)(p + i * stride);
    uint64_t base = 0, pages = 0;
    if (!page_range_admissible(d, reserved, reserved_count, &base, &pages)) continue;
    if (pmm.region_count == PMM_MAX_REGIONS) { pmm.truncated = 1; break; }
    pmm.region[pmm.region_count].base = base;
    pmm.region[pmm.region_count].pages = pages;
    pmm.region_count++;
    pmm.total_pages += pages;
  }
}

/* Returns 0 on exhaustion — a clean refusal, never a wild pointer. */
static uint64_t pmm_alloc_page(void) {
  if (pmm.limit && pmm.allocated >= pmm.limit) return 0;
  while (pmm.cursor_region < pmm.region_count) {
    if (pmm.cursor_page < pmm.region[pmm.cursor_region].pages) {
      uint64_t addr = pmm.region[pmm.cursor_region].base + pmm.cursor_page * 4096ULL;
      pmm.cursor_page++;
      pmm.allocated++;
      for (uint64_t *q = (uint64_t *)addr; q < (uint64_t *)(addr + 4096ULL); q++) *q = 0;
      return addr;
    }
    pmm.cursor_region++;
    pmm.cursor_page = 0;
  }
  return 0;
}

static int pmm_owns(uint64_t addr) {
  for (int i = 0; i < pmm.region_count; i++) {
    uint64_t b = pmm.region[i].base;
    uint64_t e = b + pmm.region[i].pages * 4096ULL;
    if (addr >= b && addr < e) return 1;
  }
  return 0;
}

/* --------------------------------------------------------------------------
 * Stage-1 EL1 translation tables. 4 KiB granule, T0SZ=25 (39-bit VA), so the
 * walk starts at level 1 with 1 GiB entries. The tables now come from the
 * allocator above rather than from .bss.
 */
#define PT_ENTRIES 512

static uint64_t *l1_table;
static uint64_t *l2_table;
static uint64_t *l3_table;

#define DESC_TABLE 0x3ULL   /* table descriptor at L1/L2 */
#define DESC_BLOCK 0x1ULL   /* block descriptor at L1/L2 */
#define DESC_PAGE  0x3ULL   /* page descriptor at L3 */

#define ATTR_IDX(n) ((uint64_t)(n) << 2)
#define ATTR_AF     (1ULL << 10)
#define ATTR_SH_IS  (3ULL << 8)     /* inner shareable */
#define ATTR_AP_RW  (0ULL << 6)     /* EL1 read/write */
#define ATTR_AP_RO  (2ULL << 6)     /* EL1 read-only */
#define ATTR_PXN    (1ULL << 53)
#define ATTR_UXN    (1ULL << 54)

/* MAIR: attr0 = Device-nGnRnE (0x00), attr1 = Normal write-back (0xFF). */
#define MAIR_VALUE 0xFF00ULL
#define MAIR_DEVICE 0
#define MAIR_NORMAL 1

#define KERNEL_REGION_BASE 0x40000000ULL          /* L1[1] covers 1..2 GiB */
#define KERNEL_L2_INDEX ((AIUEOS_KERNEL_LOAD_BASE - KERNEL_REGION_BASE) / 0x200000ULL)
#define KERNEL_L3_BASE (KERNEL_REGION_BASE + KERNEL_L2_INDEX * 0x200000ULL)

static uint64_t tcr_value(void) {
  return (25ULL)             /* T0SZ = 25 -> 39-bit VA */
       | (1ULL << 8)         /* IRGN0 = write-back write-allocate */
       | (1ULL << 10)        /* ORGN0 = write-back write-allocate */
       | (3ULL << 12)        /* SH0   = inner shareable */
       | (0ULL << 14)        /* TG0   = 4 KiB granule */
       | (25ULL << 16)       /* T1SZ */
       | (1ULL << 23)        /* EPD1  = disable TTBR1 walks (we use TTBR0 only) */
       | (1ULL << 24) | (1ULL << 26) | (3ULL << 28)
       | (2ULL << 30)        /* TG1   = 4 KiB */
       | (2ULL << 32);       /* IPS   = 40-bit intermediate physical address */
}

/* The table walker reads through the caches once the MMU is back on, but the
   tables were written while the firmware's mapping was active. Clean them by
   VA so the walk cannot observe a stale line. */
static void clean_dcache_range(const void *base, uint64_t size) {
  uint64_t addr = (uint64_t)base & ~63ULL;
  uint64_t end = (uint64_t)base + size;
  for (; addr < end; addr += 64)
    __asm__ volatile("dc cvac, %0" :: "r"(addr) : "memory");
  __asm__ volatile("dsb ish" ::: "memory");
}

/* Returns 0 if the allocator could not supply all three table pages. */
static int build_page_tables(void) {
  l1_table = (uint64_t *)pmm_alloc_page();
  l2_table = (uint64_t *)pmm_alloc_page();
  l3_table = (uint64_t *)pmm_alloc_page();
  if (!l1_table || !l2_table || !l3_table) return 0;

  /* pmm_alloc_page zeroes each page, so the tables start clean. */

  /* L1[0]: 0..1 GiB as Device memory. PL011, the GIC and the rest of the
     QEMU virt MMIO live here. Never executable. */
  l1_table[0] = DESC_BLOCK | ATTR_IDX(MAIR_DEVICE) | ATTR_AF | ATTR_AP_RW | ATTR_PXN | ATTR_UXN;

  /* L1[1]: 1..2 GiB is RAM; descend so the kernel's own 2 MiB can be split. */
  l1_table[1] = DESC_TABLE | (uint64_t)l2_table;

  /* L1[2..3]: remaining RAM as 1 GiB normal blocks, never executable. */
  for (int i = 2; i < 4; i++)
    l1_table[i] = DESC_BLOCK | ((uint64_t)i << 30) | ATTR_IDX(MAIR_NORMAL)
                | ATTR_AF | ATTR_SH_IS | ATTR_AP_RW | ATTR_PXN | ATTR_UXN;

  /* L2: 2 MiB normal blocks across 1..2 GiB, except the kernel's own block. */
  for (int i = 0; i < PT_ENTRIES; i++) {
    if ((uint64_t)i == KERNEL_L2_INDEX) continue;
    l2_table[i] = DESC_BLOCK | (KERNEL_REGION_BASE + (uint64_t)i * 0x200000ULL)
                | ATTR_IDX(MAIR_NORMAL) | ATTR_AF | ATTR_SH_IS | ATTR_AP_RW
                | ATTR_PXN | ATTR_UXN;
  }
  l2_table[KERNEL_L2_INDEX] = DESC_TABLE | (uint64_t)l3_table;

  /* L3: 4 KiB pages over the kernel image. This is the W^X split —
     text RX, rodata RO+NX, everything writable RW+NX. */
  for (int i = 0; i < PT_ENTRIES; i++) {
    uint64_t va = KERNEL_L3_BASE + (uint64_t)i * 4096ULL;
    uint64_t attrs = ATTR_IDX(MAIR_NORMAL) | ATTR_AF | ATTR_SH_IS;

#ifdef AIUEOS_BREAK_WX
    /* Negative control for the gate (never a build option for real use):
       map every kernel page writable AND privileged-executable. The probes
       then take no fault, and a gate that actually checks W^X must reject
       this build. Without this, the gate would only be proving that markers
       print — not that the permissions mean anything. */
    attrs |= ATTR_AP_RW | ATTR_UXN;
#else
    if (va >= (uint64_t)__text_start && va < (uint64_t)__text_end)
      attrs |= ATTR_AP_RO | ATTR_UXN;                 /* RX: privileged-executable */
    else if (va >= (uint64_t)__rodata_start && va < (uint64_t)__rodata_end)
      attrs |= ATTR_AP_RO | ATTR_PXN | ATTR_UXN;      /* RO + no execute */
    else
      attrs |= ATTR_AP_RW | ATTR_PXN | ATTR_UXN;      /* RW + no execute */
#endif

    l3_table[i] = DESC_PAGE | va | attrs;
  }

  /* 4096, not `sizeof l1_table` — these are pointers into allocator pages now,
     so sizeof would clean 8 bytes and silently leave the rest stale. */
  clean_dcache_range(l1_table, 4096);
  clean_dcache_range(l2_table, 4096);
  clean_dcache_range(l3_table, 4096);
  return 1;
}

static void mmu_enable(void) {
  uint64_t sctlr;

  /* Drop the firmware's mapping first. We are identity-mapped either way, so
     execution continues at the same physical address across the switch. */
  __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
  sctlr &= ~((1ULL << 0) | (1ULL << 2) | (1ULL << 12));   /* M, C, I */
  __asm__ volatile("msr sctlr_el1, %0; isb" :: "r"(sctlr) : "memory");

  __asm__ volatile("msr mair_el1, %0" :: "r"(MAIR_VALUE));
  __asm__ volatile("msr tcr_el1,  %0" :: "r"(tcr_value()));
  __asm__ volatile("msr ttbr0_el1,%0" :: "r"((uint64_t)l1_table));
  __asm__ volatile("dsb ish; tlbi vmalle1; dsb ish; isb" ::: "memory");

  __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
  sctlr |= (1ULL << 0) | (1ULL << 2) | (1ULL << 12);      /* M, C, I */
  __asm__ volatile("msr sctlr_el1, %0; isb" :: "r"(sctlr) : "memory");
}

/* --------------------------------------------------------------------------
 * Fault plumbing for the W^X probes.
 */
volatile uint64_t g_fault_count;
volatile uint64_t g_last_esr;
volatile uint64_t g_last_far;
volatile uint64_t g_recovery_pc;

/* ESR_EL1 EC values for aborts taken without a change of exception level. */
#define EC_INSTRUCTION_ABORT_SAME_EL 0x21
#define EC_DATA_ABORT_SAME_EL        0x25
#define FSC_PERMISSION_FAULT_L3      0x0F

void aiueos_exception(void) {
  uint64_t esr, far;
  __asm__ volatile("mrs %0, esr_el1" : "=r"(esr));
  __asm__ volatile("mrs %0, far_el1" : "=r"(far));

  g_last_esr = esr;
  g_last_far = far;
  g_fault_count++;

  if (g_recovery_pc) {
    __asm__ volatile("msr elr_el1, %0" :: "r"(g_recovery_pc));
    return;
  }

  /* No recovery armed: this fault was not part of a probe. Report and stop
     rather than looping on the faulting instruction. */
  serial_puts("AIUEOS_KERNEL_UNEXPECTED_FAULT esr=");
  serial_puthex(esr);
  serial_puts(" far=");
  serial_puthex(far);
  serial_puts("\n");
  for (;;) __asm__ volatile("wfi");
}

/* A valid `ret` sitting in .rodata. If PXN were NOT enforced this would
   execute and return cleanly, so the failure mode is an observable
   "no fault" line rather than a hang. */
static const uint32_t rodata_ret_instruction __attribute__((used)) = 0xd65f03c0;

static void report_fault(const char *label, uint64_t expect_ec) {
  uint64_t ec = (g_last_esr >> 26) & 0x3f;
  uint64_t fsc = g_last_esr & 0x3f;
  if (g_fault_count == 0) {
    serial_puts(label);
    serial_puts(" NO_FAULT — W^X NOT ENFORCED\n");
    return;
  }
  serial_puts(label);
  serial_puts(" ec=");
  serial_puthex(ec);
  serial_puts(fsc == FSC_PERMISSION_FAULT_L3 ? " fsc=permission-l3" : " fsc=other");
  serial_puts(ec == expect_ec ? " expected-ec" : " UNEXPECTED-EC");
  serial_puts(" far=");
  serial_puthex(g_last_far);
  serial_puts("\n");
}

void kernel_main(struct aiueos_boot_info *info) {
  serial_puts("AIUEOS_KERNEL_ENTRY\n");

  /* Boot-info admission: the handoff is rejected loudly, never assumed. */
  if (!info || info->magic != AIUEOS_BOOT_INFO_MAGIC) {
    serial_puts("AIUEOS_BOOTINFO_BAD_MAGIC\n");
    goto done;
  }
  if (info->version != AIUEOS_BOOT_INFO_VERSION) {
    serial_puts("AIUEOS_BOOTINFO_BAD_VERSION\n");
    goto done;
  }
  serial_puts("AIUEOS_BOOTINFO_OK entries=");
  serial_putdec(info->descriptor_size ? info->memory_map_size / info->descriptor_size : 0);
  serial_puts(" fb=");
  serial_puthex(info->framebuffer_base);
  serial_puts(" w=");
  serial_putdec(info->framebuffer_width);
  serial_puts(" h=");
  serial_putdec(info->framebuffer_height);
  serial_puts("\n");

  serial_puts("AIUEOS_KERNEL_IMAGE text=");
  serial_puthex((uint64_t)__text_start);
  serial_puts("..");
  serial_puthex((uint64_t)__text_end);
  serial_puts(" rodata=");
  serial_puthex((uint64_t)__rodata_start);
  serial_puts("..");
  serial_puthex((uint64_t)__rodata_end);
  serial_puts(" end=");
  serial_puthex((uint64_t)__end);
  serial_puts("\n");

  /* --- physical memory admission + allocator ---------------------------- */
  {
    /* Ranges the allocator must never hand out, even if the firmware were to
       describe them as conventional memory. */
    /* Round each range OUT to whole pages. The base is masked down, so the
       masked-off offset has to be added back to the size before rounding up —
       otherwise a base that is not page aligned under-covers its own tail by
       up to 4095 bytes. */
    uint64_t map_off = (uint64_t)info->memory_map & 0xFFFULL;
    uint64_t info_off = (uint64_t)info & 0xFFFULL;
    struct reserved_range reserved[3] = {
      {AIUEOS_KERNEL_LOAD_BASE, 0x200000ULL},                  /* kernel window */
      {(uint64_t)info & ~0xFFFULL,
       (info_off + sizeof *info + 0xFFFULL) & ~0xFFFULL},      /* boot-info page */
      {(uint64_t)info->memory_map & ~0xFFFULL,
       (map_off + info->memory_map_size + 0xFFFULL) & ~0xFFFULL} /* the map itself */
    };
    pmm_init(info, reserved, 3);

    serial_puts("AIUEOS_PMM_OK regions=");
    serial_putdec((uint64_t)pmm.region_count);
    serial_puts(" pages=");
    serial_putdec(pmm.total_pages);
    serial_puts(" mib=");
    serial_putdec(pmm.total_pages * 4096ULL / (1024ULL * 1024ULL));
    serial_puts(pmm.truncated ? " TRUNCATED\n" : "\n");

    if (pmm.region_count == 0 || pmm.total_pages == 0) {
      serial_puts("AIUEOS_PMM_NO_USABLE_MEMORY\n");
      goto done;
    }

    /* Self-test 0: the judgement held — no admitted region overlaps anything
       reserved. This is the check that catches an allocator willing to hand
       out the kernel image, the boot-info page or the memory map itself. */
    {
      int ok = 1;
      for (int i = 0; i < pmm.region_count && ok; i++) {
        uint64_t b = pmm.region[i].base;
        uint64_t e = b + pmm.region[i].pages * 4096ULL;
        for (int j = 0; j < 3; j++) {
          uint64_t r0 = reserved[j].base, r1 = reserved[j].base + reserved[j].size;
          if (b < r1 && r0 < e) { ok = 0; break; }
        }
      }
      serial_puts(ok ? "AIUEOS_PMM_RESERVED_OK\n"
                     : "AIUEOS_PMM_RESERVED_VIOLATED — allocator may hand out reserved memory\n");
      if (!ok) goto done;
    }

    /* Self-test 1: distinctness, alignment and ownership over a run of pages.
       A double-allocation is the failure this must catch. */
    {
      uint64_t seen[32];
      int n = 32, ok = 1;
      for (int i = 0; i < n; i++) {
        uint64_t p = pmm_alloc_page();
        if (!p || (p & 0xFFFULL) || !pmm_owns(p)) { ok = 0; break; }
        for (int j = 0; j < i; j++) if (seen[j] == p) { ok = 0; break; }
        if (!ok) break;
        /* pmm_alloc_page must hand back a zeroed page. */
        for (int w = 0; w < 512; w++) if (((uint64_t *)p)[w] != 0) { ok = 0; break; }
        if (!ok) break;
        seen[i] = p;
      }
      serial_puts(ok ? "AIUEOS_PMM_DISTINCT_OK n=32\n"
                     : "AIUEOS_PMM_DISTINCT_FAIL\n");
      if (!ok) goto done;
    }

    /* Self-test 2: exhaustion is a clean refusal, not a wild pointer. Capped
       with a test-only budget so this does not have to drain real RAM. */
    {
      uint64_t saved_limit = pmm.limit;
      pmm.limit = pmm.allocated + 4;
      int drained = 0, clean = 0;
      for (int i = 0; i < 4; i++) if (pmm_alloc_page()) drained++;
      clean = (pmm_alloc_page() == 0);
      pmm.limit = saved_limit;
      serial_puts((drained == 4 && clean) ? "AIUEOS_PMM_EXHAUSTION_OK\n"
                                          : "AIUEOS_PMM_EXHAUSTION_FAIL\n");
      if (!(drained == 4 && clean)) goto done;
    }
  }

  if (!build_page_tables()) {
    serial_puts("AIUEOS_PAGETABLES_ALLOC_FAIL\n");
    goto done;
  }
  serial_puts("AIUEOS_PAGETABLES_BUILT ttbr0=");
  serial_puthex((uint64_t)l1_table);
  serial_puts(pmm_owns((uint64_t)l1_table) ? " from=allocator\n" : " from=UNKNOWN\n");

  mmu_enable();

  {
    uint64_t sctlr, ttbr0;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    __asm__ volatile("mrs %0, ttbr0_el1" : "=r"(ttbr0));
    /* Reaching this line at all means instruction fetch, the stack and PL011
       are all being translated by tables this kernel built. */
    serial_puts("AIUEOS_MMU_OK sctlr=");
    serial_puthex(sctlr);
    serial_puts(" ttbr0=");
    serial_puthex(ttbr0);
    serial_puts("\n");
    if (!(sctlr & 1ULL)) serial_puts("AIUEOS_MMU_NOT_ENABLED\n");
  }

  /* W^X probe 1: store into .text, which is mapped read-only. */
  g_fault_count = 0;
  g_recovery_pc = (uint64_t)&&wx_write_done;
  {
    volatile uint32_t *text = (volatile uint32_t *)__text_start;
    *text = 0xdeadbeefu;
  }
wx_write_done:
  g_recovery_pc = 0;
  report_fault("AIUEOS_WX_WRITE_TEXT", EC_DATA_ABORT_SAME_EL);

  /* W^X probe 2: execute a byte in .rodata, which is mapped PXN. */
  g_fault_count = 0;
  g_recovery_pc = (uint64_t)&&wx_exec_done;
  {
    void (*fn)(void) = (void (*)(void))&rodata_ret_instruction;
    fn();
  }
wx_exec_done:
  g_recovery_pc = 0;
  report_fault("AIUEOS_WX_EXEC_RODATA", EC_INSTRUCTION_ABORT_SAME_EL);

  serial_puts("AIUEOS_AARCH64_KERNEL_OK\n");

done:
  /* PSCI SYSTEM_OFF — the AArch64 replacement for isa-debug-exit. */
  {
    register uint64_t x0 __asm__("x0") = 0x84000008ULL;
    __asm__ volatile("hvc #0" : "+r"(x0) :: "memory");
  }
  for (;;) __asm__ volatile("wfi");
}
