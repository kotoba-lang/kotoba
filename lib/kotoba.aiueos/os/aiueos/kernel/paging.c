#include <stdint.h>
#include <stddef.h>
#include "../include/boot_info.h"
#include "model_handoff.h"

#define PAGE_SIZE 4096ULL
#define ENTRY_COUNT 512
#define PTE_PRESENT (1ULL << 0)
#define PTE_WRITABLE (1ULL << 1)
#define PTE_USER (1ULL << 2)
#define PTE_HUGE (1ULL << 7)
#define PTE_WRITE_THROUGH (1ULL << 3)
#define PTE_CACHE_DISABLE (1ULL << 4)
#define PTE_NX (1ULL << 63)
#define CR4_PGE (1ULL << 7)
#define CR4_PCIDE (1ULL << 17)
#define CR4_CET (1ULL << 23)
#define PML4_SLOT_ZERO_LIMIT (1ULL << 39)

extern uint8_t aiueos_text_start[], aiueos_text_end[];
extern uint8_t aiueos_rodata_start[], aiueos_rodata_end[];
extern uint8_t aiueos_data_start[], aiueos_kernel_end[];
extern uint8_t aiueos_user_text_start[], aiueos_user_text_end[];
extern uint8_t aiueos_user_data_start[], aiueos_user_data_end[];
extern uint8_t aiueos_low_end[], aiueos_high_data_start[], aiueos_high_data_end[];

static uint64_t pml4[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pml5[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t pdpt[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t low_page_table[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
/* The physical K16 may hand off with control-flow enforcement enabled.  A
 * direct jump from firmware paging to the final split W^X map leaves no
 * independent place to prove whether CR3 itself loaded or the first protected
 * access faulted.  This bounded transition root maps the first GiB with 2 MiB
 * leaves, then the kernel immediately replaces it with the final split map.
 * It is never published as kernel_cr3 and cannot survive successful init.
 * The four tables live in `.high_bss` (the 4..6 MiB writable-NX window), not
 * `.bss`, so the low kernel/user layout ends at `aiueos_low_end <= 0x1f4000`:
 * 16 KiB of tables that are dead after init (4 x 4 KiB, page-aligned) sat
 * above the process-private aperture. They are reached only while the
 * firmware root is live -- zeroed and built in aiueos_paging_initialize
 * before the first owned CR3, read by observe_cr3_roundtrip under the
 * firmware root -- and the owned map covers 4..6 MiB from the first owned
 * CR3 on, so the section change is invisible to every path that touches
 * them. Same move and same justification as pci_pdpts/pci_directories below. */
static uint64_t transition_pml4[ENTRY_COUNT]
  __attribute__((section(".high_bss"), aligned(PAGE_SIZE)));
static uint64_t transition_pml5[ENTRY_COUNT]
  __attribute__((section(".high_bss"), aligned(PAGE_SIZE)));
static uint64_t transition_pdpt[ENTRY_COUNT]
  __attribute__((section(".high_bss"), aligned(PAGE_SIZE)));
static uint64_t transition_page_directory[ENTRY_COUNT]
  __attribute__((section(".high_bss"), aligned(PAGE_SIZE)));
static uint64_t apic_page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
static uint64_t framebuffer_page_directory[ENTRY_COUNT] __attribute__((aligned(PAGE_SIZE)));
#define PCI_PDPT_SLOTS 4
#define PCI_DIRECTORY_SLOTS 8
/* 48 KiB of the low region was these two arrays; they live in `.high_bss`
 * (the 4..6 MiB writable-NX window) so the production node image links under
 * `aiueos_low_end <= 0x1f4000` (ADR-0222). They are kernel-only, reached
 * through the kernel map every process space copies, and zeroed explicitly in
 * aiueos_paging_initialize while the loader's identity map is still live. */
static uint64_t pci_pdpts[PCI_PDPT_SLOTS][ENTRY_COUNT]
  __attribute__((section(".high_bss"), aligned(PAGE_SIZE)));
static uint64_t pci_directories[PCI_DIRECTORY_SLOTS][ENTRY_COUNT]
  __attribute__((section(".high_bss"), aligned(PAGE_SIZE)));
static uint16_t pci_pdpt_owner[PCI_PDPT_SLOTS];
static uint32_t pci_directory_owner[PCI_DIRECTORY_SLOTS];

/* Phase-3 address-space vertical slice.  Kernel/MMIO branches stay shared,
 * while each process owns the complete low-2MiB page-table path. */
struct process_address_space {
  uint64_t *pml5, *pml4, *pdpt, *directory, *low;
  uint8_t *private_page, *user_text_page, *user_text_page2, *user_data_page;
  uint16_t generation;
  uint8_t active, claimed;
};
#define PROCESS_SLOT_COUNT 8U
#define PROCESS_PRIVATE_BASE 0x1f4000ULL
static struct process_address_space process_spaces[PROCESS_SLOT_COUNT];
extern void *aiueos_allocate_physical_page(void);
extern int aiueos_free_physical_page(void *page);
extern uint64_t kotoba_aiueos_page_mapping_plan(uint64_t process,uint64_t kind,
  uint64_t size,uint64_t active,uint64_t existing);
/* Whether a physical range may be mapped at all is a decision and lives in
   kotoba/mmio-map-admit.kotoba; everything below is mechanism. */
extern uint64_t kotoba_aiueos_mmio_map_admit(uint64_t address, uint64_t length);
/* Which model-specific registers this kernel may reach at all is likewise a
   decision, and lives in kotoba/msr-read.kotoba and kotoba/msr-write.kotoba;
   the rdmsr/wrmsr below them is mechanism. IA32_EFER (0xc0000080) is on the
   admitted list because of the write immediately below: every entry this file
   builds carries PTE_NX, which is a reserved bit until NXE is set. */
extern uint64_t kotoba_aiueos_msr_read(uint64_t index);
extern uint64_t kotoba_aiueos_msr_write(uint64_t index, uint64_t value);
/* WHICH cpuid leaf and WHICH bit answer "does this CPU support NX" is the
   decision, and it lives in kotoba/cpu-feature-nx.kotoba -- leaf 0x80000001,
   EDX bit 20, behind a max-extended-leaf guard on leaf 0x80000000. Leaving
   those two numbers here as arguments to a generic accessor would have moved
   the `cpuid` instruction out of C while leaving the whole decision in it. */
extern uint64_t kotoba_aiueos_cpu_feature_nx(void);
int aiueos_address_space_reclaim(unsigned process);
void *aiueos_address_space_private_backing(unsigned process);
static uint64_t kernel_cr3;
static uint64_t memory_encryption_mask;
static uint64_t five_level_paging;

#ifdef AIUEOS_PHYSICAL_QUALIFICATION
extern int aiueos_qualification_progress(uint32_t code);
extern void aiueos_qualification_runtime_set_firmware_cr3(uint64_t firmware_cr3);
#define PAGING_PROGRESS(code) aiueos_qualification_progress(code)
#else
#define PAGING_PROGRESS(code) ((void)0)
#endif

static uint64_t process_private_va(unsigned process) {
  uint64_t plan=kotoba_aiueos_page_mapping_plan(process,1,PAGE_SIZE,1,0);
  return plan ? (plan>>2)*PAGE_SIZE : 0;
}

static uint64_t user_mapping_flags(uint64_t permission) {
  if (permission==1) return PTE_PRESENT|PTE_USER;
  if (permission==2) return PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX;
  return 0;
}

static uint64_t read_cr0(void) {
  uint64_t value; __asm__ volatile("mov %%cr0, %0" : "=r"(value)); return value;
}
static uint64_t read_cr3(void) {
  uint64_t value; __asm__ volatile("mov %%cr3, %0" : "=r"(value)); return value;
}
static uint64_t read_cr4(void) {
  uint64_t value; __asm__ volatile("mov %%cr4, %0" : "=r"(value)); return value;
}
static void write_cr0(uint64_t value) { __asm__ volatile("mov %0, %%cr0" : : "r"(value) : "memory"); }
static void write_cr3(uint64_t value) { __asm__ volatile("mov %0, %%cr3" : : "r"(value) : "memory"); }
static void write_cr4(uint64_t value) { __asm__ volatile("mov %0, %%cr4" : : "r"(value) : "memory"); }

/* Execute only the three register operations between address spaces.  The
 * durable marker is written after this returns under the firmware root, so a
 * physical result distinguishes a CR3/first-fetch failure from a later C call
 * or UEFI SetVariable failure under the kernel-owned map. */
static __attribute__((always_inline)) inline uint64_t
observe_cr3_roundtrip(uint64_t candidate, uint64_t firmware) {
  uint64_t observed;
  __asm__ volatile(
      "mov %[candidate], %%cr3\n\t"
      "mov %%cr3, %[observed]\n\t"
      "mov %[firmware], %%cr3"
      : [observed] "=&r"(observed)
      : [candidate] "r"(candidate), [firmware] "r"(firmware)
      : "memory");
  return observed;
}
static int within(uint64_t page, const uint8_t *start, const uint8_t *end) {
  return page >= (uint64_t)(uintptr_t)start && page < (uint64_t)(uintptr_t)end;
}

static void cpuid(uint32_t leaf, uint32_t subleaf, uint32_t *a, uint32_t *b,
                  uint32_t *c, uint32_t *d) {
  __asm__ volatile("cpuid"
                   : "=a"(*a), "=b"(*b), "=c"(*c), "=d"(*d)
                   : "a"(leaf), "c"(subleaf));
}

/* UEFI may hand off with AMD Secure Memory Encryption already active. In that
   state the C-bit in the firmware CR3 says that its root page table is stored
   encrypted. Replacing CR3 with an unmodified physical address would make the
   CPU read this kernel's encrypted PML4 as plaintext and fault immediately.
   CPUID 0x8000001f reports the C-bit position; inherit it only when the current
   firmware CR3 actually carries it, so merely supporting SME changes nothing.

   This inline CPUID is deliberately a bounded bootstrap mechanism. The normal
   feature decisions remain compiler-owned Kotoba objects; this one must read
   the live firmware CR3 and return its address modifier as one atomic handoff
   observation rather than answer a reusable policy question. */
static uint64_t inherited_memory_encryption_mask(uint64_t firmware_cr3) {
  uint32_t a, b, c, d;
  cpuid(0x80000000U, 0, &a, &b, &c, &d);
  if (a < 0x8000001fU) return 0;
  cpuid(0x8000001fU, 0, &a, &b, &c, &d);
  if ((a & 1U) == 0) return 0;
  uint32_t c_bit = b & 0x3fU;
  if (c_bit < 32U || c_bit >= 52U) return 0;
  uint64_t mask = 1ULL << c_bit;
  return firmware_cr3 & mask;
}

static uint64_t encrypted_ram_address(const void *address) {
  return (uint64_t)(uintptr_t)address | memory_encryption_mask;
}

static uint64_t encrypted_ram_page(uint64_t address) {
  return address | memory_encryption_mask;
}

#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
static int map_model_handoff(const struct aiueos_boot_info *boot) {
  struct aiueos_model_mapping_plan plan;
  if (!boot || boot->version < AIUEOS_BOOT_INFO_VERSION_MODEL_HANDOFF ||
      !boot->model_paging_base ||
      (boot->model_paging_base & (PAGE_SIZE - 1)) ||
      (boot->version < AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED &&
       boot->model_paging_pages != AIUEOS_MODEL_PAGING_PAGES) ||
      boot->model_paging_base >= 0x40000000ULL ||
      boot->model_paging_base > 0x40000000ULL -
        AIUEOS_MODEL_PAGING_PAGES * PAGE_SIZE ||
      !aiueos_model_mapping_plan(boot->model_base, boot->model_size, &plan))
    return 0;
  uint64_t (*model_page_directories)[ENTRY_COUNT] =
    (void *)(uintptr_t)boot->model_paging_base;
  for (uint32_t slot = 0; slot < AIUEOS_MODEL_MAX_PDPT_DIRECTORIES; slot++)
    for (uint32_t entry = 0; entry < ENTRY_COUNT; entry++)
      model_page_directories[slot][entry] = 0;
  for (uint32_t slot = 0; slot < plan.directory_count; slot++) {
    uint32_t pdpt_index = plan.first_pdpt + slot;
    if (pdpt_index >= ENTRY_COUNT || pdpt[pdpt_index]) return 0;
    pdpt[pdpt_index] = encrypted_ram_address(model_page_directories[slot]) |
      PTE_PRESENT | PTE_WRITABLE;
  }
  for (uint64_t page = plan.first_2m;; page += 0x200000ULL) {
    uint32_t pdpt_index = (uint32_t)(page >> 30);
    uint32_t directory_slot = pdpt_index - plan.first_pdpt;
    uint32_t page_index = (uint32_t)((page >> 21) & 0x1ffU);
    /* The leaf is deliberately not writable: after loader SHA-256 admission,
     * the native runtime receives immutable weights rather than an allocator
     * buffer it may silently modify. */
    model_page_directories[directory_slot][page_index] =
      encrypted_ram_page(page) | PTE_PRESENT | PTE_HUGE | PTE_NX;
    if (page == plan.last_2m) break;
  }
  return 1;
}
#endif

int aiueos_paging_initialize(const struct aiueos_boot_info *boot) {
  PAGING_PROGRESS(240);
  if (!kotoba_aiueos_cpu_feature_nx()) return 0;
  PAGING_PROGRESS(241);

  uint64_t firmware_cr3 = read_cr3();
  uint64_t firmware_cr4 = read_cr4();
  five_level_paging = (firmware_cr4 >> 12) & 1U;
  uint64_t inherited_cet = (firmware_cr4 & CR4_CET) ? 1U : 0U;
  uint64_t inherited_pge = (firmware_cr4 & CR4_PGE) ? 1U : 0U;
  uint64_t inherited_pcide = (firmware_cr4 & CR4_PCIDE) ? 1U : 0U;
  memory_encryption_mask = inherited_memory_encryption_mask(firmware_cr3);

  for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
    pml5[i] = pml4[i] = pdpt[i] = page_directory[i] = low_page_table[i] = 0;
    transition_pml5[i] = transition_pml4[i] = transition_pdpt[i] = 0;
    transition_page_directory[i] = 0;
    apic_page_directory[i] = 0;
    framebuffer_page_directory[i] = 0;
  }
  for (uint64_t slot = 0; slot < PCI_PDPT_SLOTS; slot++) {
    pci_pdpt_owner[slot] = UINT16_MAX;
    for (uint64_t i = 0; i < ENTRY_COUNT; i++) pci_pdpts[slot][i] = 0;
  }
  for (uint64_t slot = 0; slot < PCI_DIRECTORY_SLOTS; slot++) {
    pci_directory_owner[slot] = UINT32_MAX;
    for (uint64_t i = 0; i < ENTRY_COUNT; i++) pci_directories[slot][i] = 0;
  }
  pml4[0] = encrypted_ram_address(pdpt) | PTE_PRESENT | PTE_WRITABLE;
  pdpt[0] = encrypted_ram_address(page_directory) | PTE_PRESENT | PTE_WRITABLE;
  page_directory[0] = encrypted_ram_address(low_page_table) | PTE_PRESENT | PTE_WRITABLE;
  pml4[0] |= PTE_USER; pdpt[0] |= PTE_USER; page_directory[0] |= PTE_USER;
  if (five_level_paging)
    pml5[0] = encrypted_ram_address(pml4) | PTE_PRESENT | PTE_WRITABLE | PTE_USER;
  transition_pml4[0] = encrypted_ram_address(transition_pdpt) |
    PTE_PRESENT | PTE_WRITABLE;
  transition_pdpt[0] = encrypted_ram_address(transition_page_directory) |
    PTE_PRESENT | PTE_WRITABLE;
  if (five_level_paging)
    transition_pml5[0] = encrypted_ram_address(transition_pml4) |
      PTE_PRESENT | PTE_WRITABLE;
  for (uint64_t i = 1; i < ENTRY_COUNT; i++) {
    page_directory[i] = encrypted_ram_page(i * 0x200000ULL) |
      PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX;
  }
  for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
    transition_page_directory[i] = encrypted_ram_page(i * 0x200000ULL) |
      PTE_PRESENT | PTE_WRITABLE | PTE_HUGE;
  }
  pdpt[3] = encrypted_ram_address(apic_page_directory) | PTE_PRESENT | PTE_WRITABLE;
  const uint64_t apic_base = 0xfee00000ULL;
  const uint64_t apic_pde = (apic_base >> 21) & 0x1ff;
  apic_page_directory[apic_pde] = apic_base | PTE_PRESENT | PTE_WRITABLE |
    PTE_HUGE | PTE_NX | PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
  const uint64_t ioapic_base = 0xfec00000ULL;
  const uint64_t ioapic_pde = (ioapic_base >> 21) & 0x1ff;
  apic_page_directory[ioapic_pde] = ioapic_base | PTE_PRESENT | PTE_WRITABLE |
    PTE_HUGE | PTE_NX | PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  if (!map_model_handoff(boot)) return 0;
#else
  (void)boot;
#endif
  for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
    uint64_t page = i * PAGE_SIZE;
    uint64_t flags = PTE_PRESENT | PTE_NX;
    if (!within(page, aiueos_text_start, aiueos_text_end) &&
        !within(page, aiueos_rodata_start, aiueos_rodata_end)) flags |= PTE_WRITABLE;
    if (within(page, aiueos_text_start, aiueos_text_end)) flags &= ~PTE_NX;
    if (within(page, aiueos_user_text_start, aiueos_user_text_end))
      flags = PTE_PRESENT | PTE_USER;
    if (within(page, aiueos_user_data_start, aiueos_user_data_end))
      flags = PTE_PRESENT | PTE_USER | PTE_WRITABLE | PTE_NX;
    if (page == (uint64_t)(uintptr_t)aiueos_user_data_end) flags = 0;
    low_page_table[i] = encrypted_ram_page(page) | flags;
  }
  low_page_table[(uint64_t)(uintptr_t)aiueos_user_data_end / PAGE_SIZE] = 0;
  PAGING_PROGRESS(242);

  /* This is the one MSR read in the kernel whose result is not examined before
     use -- it is ORed with NXE and written straight back -- so a refused read
     returning 0 would clear LME and SCE here. That is why EFER is admitted, and
     why the write's status is checked rather than discarded. */
  if (!kotoba_aiueos_msr_write(0xc0000080ULL,
                               kotoba_aiueos_msr_read(0xc0000080ULL) | (1ULL << 11)))
    return 0;
  PAGING_PROGRESS(243);
  write_cr0(read_cr0() | (1ULL << 16));
  PAGING_PROGRESS(244);
  /* Normalize firmware-owned translation controls before the first owned CR3.
     PCIDE may only be cleared with a zero PCID, so first reload the same
     firmware root with CR3[11:0] clear and teach the qualification recorder
     that normalized value.  Clearing PGE flushes inherited global entries;
     clearing CET removes the firmware-owned shadow stack. */
  uint64_t paging_features = five_level_paging |
    (memory_encryption_mask ? 2U : 0U) | (inherited_cet ? 4U : 0U) |
    (inherited_pge ? 8U : 0U) | (inherited_pcide ? 16U : 0U);
  PAGING_PROGRESS((uint32_t)(320U + paging_features));
  if (inherited_pcide) {
    firmware_cr3 &= ~0xfffULL;
    write_cr3(firmware_cr3);
#ifdef AIUEOS_PHYSICAL_QUALIFICATION
    aiueos_qualification_runtime_set_firmware_cr3(firmware_cr3);
#endif
  }
  uint64_t normalized_cr4 = firmware_cr4 & ~(CR4_CET | CR4_PGE | CR4_PCIDE);
  if (normalized_cr4 != firmware_cr4) write_cr4(normalized_cr4);
  if (read_cr4() & (CR4_CET | CR4_PGE | CR4_PCIDE)) return 0;
  PAGING_PROGRESS((uint32_t)(352U + paging_features));
  uint64_t transition_root = encrypted_ram_address(
    five_level_paging ? (const void *)transition_pml5 : (const void *)transition_pml4);
  uint64_t root = encrypted_ram_address(five_level_paging ? (const void *)pml5
                                                         : (const void *)pml4);
  if (observe_cr3_roundtrip(transition_root, firmware_cr3) != transition_root)
    return 0;
  PAGING_PROGRESS((uint32_t)(384U + paging_features));
  if (observe_cr3_roundtrip(root, firmware_cr3) != root) return 0;
  PAGING_PROGRESS((uint32_t)(416U + paging_features));
  write_cr3(root);
  kernel_cr3 = root;
  PAGING_PROGRESS((uint32_t)(448U + paging_features));

  uint64_t text_index = (uint64_t)(uintptr_t)aiueos_text_start / PAGE_SIZE;
  uint64_t rodata_index = (uint64_t)(uintptr_t)aiueos_rodata_start / PAGE_SIZE;
  uint64_t data_index = (uint64_t)(uintptr_t)aiueos_data_start / PAGE_SIZE;
  if (text_index >= ENTRY_COUNT || rodata_index >= ENTRY_COUNT || data_index >= ENTRY_COUNT) return 0;
  int valid = read_cr3() == root &&
         !(low_page_table[text_index] & PTE_WRITABLE) && !(low_page_table[text_index] & PTE_NX) &&
         !(low_page_table[rodata_index] & PTE_WRITABLE) && (low_page_table[rodata_index] & PTE_NX) &&
         (low_page_table[data_index] & PTE_WRITABLE) && (low_page_table[data_index] & PTE_NX) &&
         (uint64_t)(uintptr_t)aiueos_low_end <= PROCESS_PRIVATE_BASE &&
         (uint64_t)(uintptr_t)aiueos_high_data_start >= 0x400000ULL &&
         (uint64_t)(uintptr_t)aiueos_high_data_end <= 0x600000ULL &&
         (uint64_t)(uintptr_t)aiueos_kernel_end <= 0x600000ULL &&
         (page_directory[2] & (PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX)) ==
           (PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX);
  if (valid) PAGING_PROGRESS((uint32_t)(480U + paging_features));
  return valid;
}

static void release_process_space(struct process_address_space *space) {
  if (space->private_page) aiueos_free_physical_page(space->private_page);
  if (space->user_text_page) aiueos_free_physical_page(space->user_text_page);
  if (space->user_text_page2) aiueos_free_physical_page(space->user_text_page2);
  if (space->user_data_page) aiueos_free_physical_page(space->user_data_page);
  if (space->low) aiueos_free_physical_page(space->low);
  if (space->directory) aiueos_free_physical_page(space->directory);
  if (space->pdpt) aiueos_free_physical_page(space->pdpt);
  if (space->pml4) aiueos_free_physical_page(space->pml4);
  if (space->pml5) aiueos_free_physical_page(space->pml5);
  uint16_t generation=space->generation;
  *space=(struct process_address_space){0};
  space->generation=generation;
}
static int initialize_process_space(unsigned process) {
    if (process>=PROCESS_SLOT_COUNT) return 0;
    struct process_address_space *space=&process_spaces[process];
    uint64_t private_va=process_private_va(process);
    uint64_t private_plan=kotoba_aiueos_page_mapping_plan(process,1,PAGE_SIZE,1,0);
    if (!private_va || !private_plan) return 0;
    if (five_level_paging && !space->pml5) space->pml5=aiueos_allocate_physical_page();
    if (!space->pml4) space->pml4=aiueos_allocate_physical_page();
    if (!space->pdpt) space->pdpt=aiueos_allocate_physical_page();
    if (!space->directory) space->directory=aiueos_allocate_physical_page();
    if (!space->low) space->low=aiueos_allocate_physical_page();
    if (!space->private_page) space->private_page=aiueos_allocate_physical_page();
    if ((five_level_paging && !space->pml5) || !space->pml4 || !space->pdpt ||
        !space->directory || !space->low || !space->private_page) {
      release_process_space(space); return 0;
    }
    for (uint64_t i = 0; i < ENTRY_COUNT; i++) {
      if (space->pml5) space->pml5[i] = pml5[i];
      space->pml4[i] = pml4[i];
      space->pdpt[i] = pdpt[i];
      space->directory[i] = page_directory[i];
      space->low[i] = low_page_table[i];
    }
    for (uint64_t i = 0; i < PAGE_SIZE; i++) space->private_page[i] = 0;
    if (space->pml5)
      space->pml5[0] = encrypted_ram_address(space->pml4) |
        PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    space->pml4[0] = encrypted_ram_address(space->pdpt) |
      PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    space->pdpt[0] = encrypted_ram_address(space->directory) |
      PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    space->directory[0] = encrypted_ram_address(space->low) |
      PTE_PRESENT | PTE_WRITABLE | PTE_USER;
    /* Neither process can name the other's page. */
    for (unsigned slot=0;slot<PROCESS_SLOT_COUNT;slot++)
      space->low[process_private_va(slot) / PAGE_SIZE] = 0;
    space->low[private_va / PAGE_SIZE] =
      encrypted_ram_address(space->private_page) |
      user_mapping_flags(private_plan&3U);
    space->active=1;
    space->claimed=0;
    space->generation++;
    if (!space->generation) space->generation=1;
    return 1;
}
int aiueos_address_spaces_initialize(void) {
  for (unsigned process=0;process<2;process++) {
    if (!initialize_process_space(process)) return 0;
  }
  return (uint64_t)(uintptr_t)process_spaces[0].pml4 !=
      (uint64_t)(uintptr_t)process_spaces[1].pml4 &&
    process_spaces[0].low[process_private_va(1) / PAGE_SIZE] == 0 &&
    process_spaces[1].low[process_private_va(0) / PAGE_SIZE] == 0;
}

int aiueos_address_space_allocate(void) {
  for (unsigned process=0;process<PROCESS_SLOT_COUNT;process++)
    if (!process_spaces[process].active)
      return initialize_process_space(process) ? (int)process : -1;
  return -1;
}
int aiueos_address_space_claim(void) {
  for (unsigned process=0;process<PROCESS_SLOT_COUNT;process++)
    if (process_spaces[process].active && !process_spaces[process].claimed) {
      process_spaces[process].claimed=1;
      return (int)process;
    }
  int process=aiueos_address_space_allocate();
  if (process>=0) process_spaces[process].claimed=1;
  return process;
}
unsigned aiueos_address_space_capacity(void) { return PROCESS_SLOT_COUNT; }
uint16_t aiueos_address_space_generation(unsigned process) {
  return process<PROCESS_SLOT_COUNT ? process_spaces[process].generation : 0;
}
int aiueos_address_space_slot_self_test(void) {
  uint16_t generation_before=aiueos_address_space_generation(2);
  for (unsigned expected=2;expected<PROCESS_SLOT_COUNT;expected++)
    if (aiueos_address_space_allocate()!=(int)expected) return 0;
  if (aiueos_address_space_allocate()!=-1) return 0;
  for (unsigned slot=2;slot<PROCESS_SLOT_COUNT;slot++)
    if (!aiueos_address_space_reclaim(slot)) return 0;
  int reused=aiueos_address_space_allocate();
  if (reused!=2 || aiueos_address_space_generation(2)<=generation_before) return 0;
  uint8_t *page=aiueos_address_space_private_backing(2);
  if (!page) return 0;
  for (uint64_t i=0;i<PAGE_SIZE;i++) if (page[i]) return 0;
  return aiueos_address_space_reclaim(2);
}

uint64_t aiueos_address_space_enter(unsigned process) {
  if (process >= PROCESS_SLOT_COUNT || !process_spaces[process].active) return 0;
  write_cr3(encrypted_ram_address(five_level_paging ?
    (const void *)process_spaces[process].pml5 :
    (const void *)process_spaces[process].pml4));
  return read_cr3();
}

void aiueos_address_space_leave(void) { write_cr3(kernel_cr3); }
uint64_t aiueos_address_space_kernel_cr3(void) { return kernel_cr3; }
uint64_t aiueos_address_space_cr3(unsigned process) {
  return process < PROCESS_SLOT_COUNT && process_spaces[process].active ?
    encrypted_ram_address(five_level_paging ?
      (const void *)process_spaces[process].pml5 :
      (const void *)process_spaces[process].pml4) : 0;
}
uint64_t aiueos_address_space_current_cr3(void) { return read_cr3(); }
void aiueos_address_space_switch(uint64_t cr3) { if (cr3) write_cr3(cr3); }
uint64_t aiueos_address_space_private_va(unsigned process) {
  return process_private_va(process);
}
void *aiueos_address_space_private_backing(unsigned process) {
  return process < PROCESS_SLOT_COUNT && process_spaces[process].active ?
    process_spaces[process].private_page : 0;
}
int aiueos_address_space_map_user_image(unsigned process,const uint8_t *text,
    uint64_t text_size,const uint8_t *data,uint64_t data_size,uint64_t data_va) {
  if (process>=PROCESS_SLOT_COUNT || !text || !data) return 0;
  /* JUN-145 ④: text takes one or two pages, data one. The plan admits text
     up to 8 KiB and names the base page (481); how many pages that is for a
     given text_size is arithmetic, not a second decision. Fail closed past
     the two pages the validator admits, and past one page for data (every
     shipped user context segment is the 88-byte record). The pairing of a
     two-page text with a data VA outside those text pages is proved by
     aiueos-user-elf-valid's contiguity rule before mapping runs, so the
     data map below can never land on top of a text page. */
  if (text_size>2*PAGE_SIZE || data_size>PAGE_SIZE) return 0;
  struct process_address_space *space=&process_spaces[process];
  uint64_t existing=space->user_text_page || space->user_data_page;
  uint64_t text_plan=kotoba_aiueos_page_mapping_plan(process,2,text_size,
    space->active,existing);
  uint64_t data_plan=kotoba_aiueos_page_mapping_plan(process,3,data_va,
    space->active,existing);
  if (!text_plan || !data_plan) return 0;
  uint64_t text_pages=(text_size+PAGE_SIZE-1)/PAGE_SIZE;
  space->user_text_page=aiueos_allocate_physical_page();
  if (text_pages==2) space->user_text_page2=aiueos_allocate_physical_page();
  space->user_data_page=aiueos_allocate_physical_page();
  if (!space->user_text_page || !space->user_data_page ||
      (text_pages==2 && !space->user_text_page2)) {
    if (space->user_text_page) aiueos_free_physical_page(space->user_text_page);
    if (space->user_text_page2) aiueos_free_physical_page(space->user_text_page2);
    if (space->user_data_page) aiueos_free_physical_page(space->user_data_page);
    space->user_text_page=space->user_text_page2=space->user_data_page=0;
    return 0;
  }
  for (uint64_t i=0;i<text_size;i++)
    (i<PAGE_SIZE ? space->user_text_page : space->user_text_page2)[i%PAGE_SIZE]
      =text[i];
  for (uint64_t i=0;i<data_size;i++) space->user_data_page[i]=data[i];
  space->low[text_plan>>2]=encrypted_ram_address(space->user_text_page)|
    user_mapping_flags(text_plan&3U);
  if (text_pages==2)
    space->low[(text_plan>>2)+1]=encrypted_ram_address(space->user_text_page2)|
      user_mapping_flags(text_plan&3U);
  space->low[data_plan>>2]=encrypted_ram_address(space->user_data_page)|
    user_mapping_flags(data_plan&3U);
  return 1;
}
void *aiueos_address_space_user_data_backing(unsigned process) {
  return process<PROCESS_SLOT_COUNT ? process_spaces[process].user_data_page : 0;
}
int aiueos_address_space_user_entry_valid(unsigned process,uint64_t entry) {
  if (process>=PROCESS_SLOT_COUNT) return 0;
  return (int)kotoba_aiueos_page_mapping_plan(process,4,entry,
    process_spaces[process].active,process_spaces[process].user_text_page!=0);
}
int aiueos_address_space_reclaim(unsigned process) {
  if (process>=PROCESS_SLOT_COUNT || !process_spaces[process].active) return 0;
  release_process_space(&process_spaces[process]);
  return 1;
}
int aiueos_address_space_reuse(unsigned process) {
  if (process>=PROCESS_SLOT_COUNT || process_spaces[process].active) return 0;
  if (!initialize_process_space(process)) return 0;
  for (uint64_t i=0;i<PAGE_SIZE;i++) if (process_spaces[process].private_page[i]) return 0;
  return 1;
}

/* GOP memory is mapped supervisor-only, non-executable and uncached.  Its
 * dedicated directory prevents a display capability from replacing RAM or
 * PCI transport mappings.  Firmware may place an integrated-GPU aperture at
 * any address in PML4 slot zero; the physical K16 reports 0x7fe0000000, so a
 * legacy below-3-GiB limit would reject its valid GOP handoff. */
int aiueos_map_framebuffer(uint64_t address, uint64_t length) {
  if (!length || address < 0x40000000ULL ||
      address >= PML4_SLOT_ZERO_LIMIT || address + length < address ||
      address + length > PML4_SLOT_ZERO_LIMIT)
    return 0;
  uint64_t pdpt_index = (address >> 30) & 0x1ff;
  if (!pdpt_index ||
      pdpt_index != (((address + length - 1) >> 30) & 0x1ff) ||
      pdpt[pdpt_index])
    return 0;
  pdpt[pdpt_index] = encrypted_ram_address(framebuffer_page_directory) |
    PTE_PRESENT | PTE_WRITABLE;
  uint64_t first = address & ~0x1fffffULL;
  uint64_t last = (address + length - 1) & ~0x1fffffULL;
  for (uint64_t page = first;; page += 0x200000ULL) {
    uint64_t index = (page >> 21) & 0x1ff;
    framebuffer_page_directory[index] = page | PTE_PRESENT | PTE_WRITABLE |
      PTE_HUGE | PTE_NX | PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
    if (page == last) break;
  }
  write_cr3(read_cr3());
  return 1;
}

int aiueos_user_mapping_verify(void) {
  uint64_t tx = (uint64_t)(uintptr_t)aiueos_user_text_start / PAGE_SIZE;
  uint64_t rw = (uint64_t)(uintptr_t)aiueos_user_data_start / PAGE_SIZE;
  uint64_t guard = (uint64_t)(uintptr_t)aiueos_user_data_end / PAGE_SIZE;
  if (tx >= ENTRY_COUNT || rw >= ENTRY_COUNT || guard >= ENTRY_COUNT) return 0;
  int result = 0;
  if ((low_page_table[tx] & (PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX)) ==
      (PTE_PRESENT|PTE_USER)) result |= 1;
  if ((low_page_table[rw] & (PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX)) ==
      (PTE_PRESENT|PTE_USER|PTE_WRITABLE|PTE_NX)) result |= 2;
  if (!low_page_table[guard]) result |= 4;
  return result;
}

int aiueos_paging_seal_ap_trampoline(void) {
  const uint64_t index = 0x8000ULL / PAGE_SIZE;
  if ((low_page_table[index] & PTE_PRESENT) == 0) return 0;
  low_page_table[index] &= ~(PTE_WRITABLE | PTE_NX);
  write_cr3(read_cr3());
  return (low_page_table[index] & (PTE_WRITABLE | PTE_NX)) == 0;
}

/* Map PCI MMIO in the already-owned top GiB using 2 MiB UC/NX pages.  Keep
 * the interface deliberately narrow: PCI must never turn an arbitrary BAR
 * into an executable or cached mapping. */
static uint64_t *pci_resolve_pdpt(uint64_t pml4_index) {
  if (pml4_index == 0) return pdpt;
  for (uint64_t slot = 0; slot < PCI_PDPT_SLOTS; slot++) {
    if (pci_pdpt_owner[slot] == pml4_index) return pci_pdpts[slot];
  }
  if (pml4[pml4_index]) return 0;
  for (uint64_t slot = 0; slot < PCI_PDPT_SLOTS; slot++) {
    if (pci_pdpt_owner[slot] == UINT16_MAX) {
      pci_pdpt_owner[slot] = (uint16_t)pml4_index;
      pml4[pml4_index] = encrypted_ram_address(pci_pdpts[slot]) |
        PTE_PRESENT | PTE_WRITABLE;
      return pci_pdpts[slot];
    }
  }
  return 0;
}

static uint64_t *pci_known_directory(uint64_t entry) {
  uint64_t address = (entry & 0x000ffffffffff000ULL) & ~memory_encryption_mask;
  if (address == (uint64_t)(uintptr_t)apic_page_directory) return apic_page_directory;
  if (address == (uint64_t)(uintptr_t)framebuffer_page_directory) return framebuffer_page_directory;
  for (uint64_t slot = 0; slot < PCI_DIRECTORY_SLOTS; slot++)
    if (address == (uint64_t)(uintptr_t)pci_directories[slot]) return pci_directories[slot];
  return 0;
}

int aiueos_map_pci_mmio(uint64_t address, uint64_t length) {
  if (!kotoba_aiueos_mmio_map_admit(address, length)) return 0;
  uint64_t pml4_index = address >> 39;
  uint64_t pdpt_index = (address >> 30) & 0x1ff;
  uint64_t *target_pdpt = pci_resolve_pdpt(pml4_index);
  if (!target_pdpt) return 0;
  uint64_t *directory = 0;
  if (target_pdpt[pdpt_index]) directory = pci_known_directory(target_pdpt[pdpt_index]);
  else {
    uint32_t owner = (uint32_t)((pml4_index << 9) | pdpt_index);
    for (uint64_t slot = 0; slot < PCI_DIRECTORY_SLOTS; slot++) {
      if (pci_directory_owner[slot] == UINT32_MAX) {
        pci_directory_owner[slot] = owner;
        directory = pci_directories[slot];
        target_pdpt[pdpt_index] = encrypted_ram_address(directory) |
          PTE_PRESENT | PTE_WRITABLE;
        break;
      }
    }
  }
  if (!directory) return 0; /* Never traverse an unowned page-table pointer. */
  uint64_t first = address & ~0x1fffffULL;
  uint64_t last = (address + length - 1) & ~0x1fffffULL;
  for (uint64_t page = first;; page += 0x200000ULL) {
    uint64_t index = (page >> 21) & 0x1ff;
    uint64_t prior = directory[index];
    uint64_t wanted = page | PTE_PRESENT | PTE_WRITABLE | PTE_HUGE | PTE_NX |
      PTE_WRITE_THROUGH | PTE_CACHE_DISABLE;
    if (prior && (prior & 0x000fffffffe00000ULL) != page) return 0;
    directory[index] = wanted;
    __asm__ volatile("invlpg (%0)" : : "r"((void *)(uintptr_t)page) : "memory");
    if (page == last) break;
  }
  return 1;
}
