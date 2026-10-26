/* 64-bit Multiboot landing. Proves the Multiboot boot path reaches long mode,
 * parses the bootloader-provided memory map, and runs the compiler-emitted
 * Kotoba probe object — the same object the UEFI path admits — before a
 * deterministic QEMU exit. This is the narrow first Multiboot vertical slice:
 * it does not stand up ACPI, virtio, GOP, or the full evidence gate, which the
 * UEFI path owns. */

#include <stdint.h>

#define MULTIBOOT_BOOTLOADER_MAGIC 0x2BADB002u
#define MULTIBOOT_INFO_MMAP 0x00000040u
#define MULTIBOOT2_BOOTLOADER_MAGIC 0x36D76289u
#define MULTIBOOT2_TAG_END 0u
#define MULTIBOOT2_TAG_MMAP 6u
#define MULTIBOOT2_TAG_FRAMEBUFFER 8u
#define MULTIBOOT2_TAG_ACPI_OLD 14u
#define MULTIBOOT2_TAG_ACPI_NEW 15u

struct multiboot_info {
  uint32_t flags;
  uint32_t mem_lower, mem_upper;
  uint32_t boot_device;
  uint32_t cmdline;
  uint32_t mods_count, mods_addr;
  uint32_t syms[4];
  uint32_t mmap_length, mmap_addr;
};

struct multiboot_mmap_entry {
  uint32_t size;
  uint64_t addr;
  uint64_t len;
  uint32_t type;
} __attribute__((packed));

extern uint64_t kotoba_aiueos_probe(void);
extern int aiueos_acpi_initialize(const void *rsdp_pointer);
extern uint32_t aiueos_acpi_cpu_count(void);
extern int aiueos_apic_timer_initialize(void);
extern volatile uint64_t aiueos_apic_timer_ticks;
extern void aiueos_mb_isr_timer(void);
extern uint8_t aiueos_mb_isr_stubs[];  /* 256 stubs, 16-byte stride */
#define MB_ISR_STUB_STRIDE 16u
extern void aiueos_mb_load_idt(const void *pointer);

struct __attribute__((packed)) idt_gate {
  uint16_t offset_low, selector;
  uint8_t ist, attributes;
  uint16_t offset_middle;
  uint32_t offset_high, reserved;
};
struct __attribute__((packed)) idt_pointer { uint16_t limit; uint64_t base; };
static struct idt_gate multiboot_idt[256];

static void set_gate(uint32_t vector, void (*handler)(void)) {
  uint64_t address = (uint64_t)(uintptr_t)handler;
  multiboot_idt[vector].offset_low = (uint16_t)address;
  multiboot_idt[vector].selector = 0x08;   /* 64-bit code segment in the Multiboot GDT */
  multiboot_idt[vector].ist = 0;
  multiboot_idt[vector].attributes = 0x8E; /* present, DPL0, interrupt gate */
  multiboot_idt[vector].offset_middle = (uint16_t)(address >> 16);
  multiboot_idt[vector].offset_high = (uint32_t)(address >> 32);
  multiboot_idt[vector].reserved = 0;
}

static inline void out8(uint16_t port, uint8_t value) {
  __asm__ volatile("outb %0, %1" : : "a"(value), "Nd"(port));
}
static inline uint8_t in8(uint16_t port) {
  uint8_t value;
  __asm__ volatile("inb %1, %0" : "=a"(value) : "Nd"(port));
  return value;
}
static void debug_string(const char *text) {
  while (*text) out8(0xe9, (uint8_t)*text++);
}
static void serial_init(void) {
  out8(0x3f8 + 1, 0x00);
  out8(0x3f8 + 3, 0x80);
  out8(0x3f8 + 0, 0x01);
  out8(0x3f8 + 1, 0x00);
  out8(0x3f8 + 3, 0x03);
  out8(0x3f8 + 2, 0xc7);
  out8(0x3f8 + 4, 0x0b);
}
static void serial_string(const char *text) {
  while (*text) {
    uint32_t budget = 1000000;
    while (!(in8(0x3f8 + 5) & 0x20) && --budget) {}
    if (budget) out8(0x3f8, (uint8_t)*text++);
    else text++;
  }
}
static void serial_hex(uint64_t value, uint32_t digits) {
  static const char hex[] = "0123456789abcdef";
  char text[17];
  if (digits > 16) digits = 16;
  for (uint32_t i = 0; i < digits; i++)
    text[digits - 1 - i] = hex[(value >> (4 * i)) & 0xfu];
  text[digits] = 0;
  serial_string(text);
  debug_string(text);
}
static void serial_decimal(uint64_t value) {
  char text[21];
  uint32_t length = 0;
  do { text[length++] = (char)('0' + (value % 10u)); value /= 10u; } while (value);
  char reversed[21];
  for (uint32_t i = 0; i < length; i++) reversed[i] = text[length - 1 - i];
  reversed[length] = 0;
  serial_string(reversed);
  debug_string(reversed);
}
__attribute__((noreturn)) static void qemu_exit(uint32_t value) {
  __asm__ volatile("outl %0, $0xf4" : : "a"(value));
  __asm__ volatile("cli");
  for (;;) __asm__ volatile("hlt");
}

/* Every vector except the timer lands here through its per-vector stub in
 * entry.S. Report what actually fired before the deterministic exit: without
 * the vector number, an unexpected interrupt is indistinguishable from any
 * other, which is exactly how this gate stayed red without a diagnosis.
 *
 * The stubs push a dummy error code for the vectors the CPU does not push one
 * for. That rule is right for EXCEPTIONS but not for an external interrupt
 * delivered on one of the ten error-code vectors, which pushes nothing -- and
 * that is precisely the case this handler was written to catch, so it must not
 * mis-report it. The frame is self-checking: the interrupted CS can only be the
 * Multiboot GDT's code selector, so a CS that is not 0x08 means the frame is
 * shifted by one slot and the pushed "error code" is really the RIP. */
__attribute__((noreturn))
void aiueos_mb_report_unexpected_vector(uint64_t vector, uint64_t error,
                                        uint64_t rip, uint64_t cs,
                                        uint64_t rflags, uint64_t cr2) {
  int has_error = ((cs & 0xfff8u) == 0x08u);
  if (!has_error) { rflags = cs; cs = rip; rip = error; error = 0; }
  /* Which legacy 8259 line, if any, is in service -- OCW3 read of the ISR.
     An external interrupt arriving here almost always came from there. */
  out8(0x20, 0x0b); uint8_t pic_master_isr = in8(0x20);
  out8(0xa0, 0x0b); uint8_t pic_slave_isr = in8(0xa0);

  serial_string("AIUEOS_MULTIBOOT_FAIL unexpected-vector vector=");
  debug_string("AIUEOS_MULTIBOOT_FAIL unexpected-vector vector=");
  serial_decimal(vector);
  if (has_error) { serial_string(" error=0x"); debug_string(" error=0x"); serial_hex(error, 8); }
  else { serial_string(" error=none-external-interrupt");
         debug_string(" error=none-external-interrupt"); }
  serial_string(" rip=0x");    debug_string(" rip=0x");    serial_hex(rip, 16);
  serial_string(" cs=0x");     debug_string(" cs=0x");     serial_hex(cs, 4);
  serial_string(" rflags=0x"); debug_string(" rflags=0x"); serial_hex(rflags, 8);
  serial_string(" cr2=0x");    debug_string(" cr2=0x");    serial_hex(cr2, 16);
  serial_string(" pic-isr=0x");debug_string(" pic-isr=0x");
  serial_hex(((uint64_t)pic_slave_isr << 8) | pic_master_isr, 4);
  serial_string("\r\n");
  debug_string("\n");
  qemu_exit(0x6d);
}

/* Locate the ACPI RSDP the firmware-independent way: the 8-byte "RSD PTR "
 * signature on a 16-byte boundary in the 0xE0000-0xFFFFF BIOS area with a
 * valid legacy 20-byte checksum. On the Multiboot path there is no UEFI
 * configuration table to hand it over. The EBDA is not scanned: QEMU's
 * built-in Multiboot loader runs no firmware, so the BDA EBDA pointer at
 * 0x40E is unpopulated; QEMU places the RSDP in this ROM window. */
static const void *find_rsdp(void) {
  static const char sig[8] = {'R', 'S', 'D', ' ', 'P', 'T', 'R', ' '};
  for (uint32_t addr = 0xE0000u; addr + 20 <= 0x100000u; addr += 16) {
    const uint8_t *candidate = (const uint8_t *)(uintptr_t)addr;
    int match = 1;
    for (int i = 0; i < 8; i++) if (candidate[i] != (uint8_t)sig[i]) { match = 0; break; }
    if (!match) continue;
    uint8_t sum = 0;
    for (int i = 0; i < 20; i++) sum = (uint8_t)(sum + candidate[i]);
    if (sum == 0) return candidate;
  }
  return 0;
}

/* Quiet the legacy 8259 pair before any `sti`.
 *
 * Measured (2026-08-06, QEMU 10.0.3 q35): reaching this point the master PIC's
 * mask is 0xb8 and the slave's is 0x8e -- IRQ0, 1, 2, 6, 8, 12, 13, 14 all
 * UNMASKED, with the master's vector base at 0x08, and the Local APIC's LINT0
 * is 0x8700: ExtINT delivery, not masked. Nothing on this path ever programmed
 * any of that. QEMU's `-kernel` Multiboot support still runs SeaBIOS, which
 * programs the 8259s and leaves the 8254 channel 0 ticking at ~18.2 Hz, then
 * hands off; the Multiboot kernel inherits a live legacy interrupt controller
 * and never touches it. So the first PIT tick after `sti` was delivered
 * through LINT0 as an ExtINT and INTA-cycled to vector 0x08 + IRQ0 = 8, which
 * the fail-fast handler correctly rejected. Whether that beat the Local APIC
 * timer's own vector-32 tick was a race, which is why this gate failed
 * intermittently (measured 1 in 8 at 85bb9f4) rather than every time.
 *
 * The vector bases are moved before masking: not because a masked PIC delivers
 * anything, but so that if a line is ever unmasked the resulting vector is
 * reported as itself instead of aliasing onto a CPU exception vector (IRQ0
 * masquerading as #DF is what made this failure so opaque) or onto a vector
 * this kernel has already given a meaning.
 *
 * The sequence itself -- ICW1..ICW4, the port-0x80 delay between writes, and
 * OCW1 -- is now kotoba/pic-disable.kotoba, called from here and from
 * kernel/main.c on the UEFI path. It was C in only one of the two, and the
 * UEFI path had the same latent gap: it never masks the PIC either, and is
 * green only because OVMF does it before handoff. What is left here is
 * mechanism with no authority over the decision.
 *
 * The bases are 0xe0/0xe8, not the 0xf0/0xf8 this function used to write. The
 * object refuses 0xf8, and it is right to: 0xf8+7 is 255, which apic.c:42
 * programs as the Local APIC's SPURIOUS vector, so an unmasked IRQ15 would
 * have been indistinguishable from a spurious interrupt -- the same masquerade
 * one chip over. 0xe0/0xe8 spans 224..239, clear of 32-35, 128 and 255. */
extern uint64_t kotoba_aiueos_pic_disable(uint64_t master_base,
                                          uint64_t slave_base);
static int legacy_pic_disable(void) {
  return kotoba_aiueos_pic_disable(0xe0, 0xe8) != 0;
}

/* Quiet the legacy PIC, install the minimal IDT (every vector -> its fail-fast
 * reporting stub, vector 32 -> the timer ISR), and bring up the Local APIC
 * periodic timer through the shared apic.c, waiting for a real vector-32
 * hardware tick. Shared by both the QEMU-direct MB1 path and the GRUB MB2
 * path. Returns 1 on a tick. */
static int install_idt_and_time_lapic(void) {
  /* Reported here rather than folded into the caller's "apic-timer" failure:
     a refused base pair is a build-time mistake in the two constants above,
     and it must not arrive wearing the name of a timer that never ticked. */
  if (!legacy_pic_disable()) {
    serial_string("AIUEOS_MULTIBOOT_FAIL pic-disable-refused\r\n");
    return 0;
  }
  for (uint32_t vector = 0; vector < 256; vector++)
    set_gate(vector, (void (*)(void))(void *)
                     (aiueos_mb_isr_stubs + (uint64_t)vector * MB_ISR_STUB_STRIDE));
  set_gate(32, aiueos_mb_isr_timer);
  struct idt_pointer idtr = { (uint16_t)(sizeof(multiboot_idt) - 1),
                              (uint64_t)(uintptr_t)multiboot_idt };
  aiueos_mb_load_idt(&idtr);
  if (!aiueos_apic_timer_initialize()) return 0;
  __asm__ volatile("sti");
  for (uint32_t budget = 0; budget < 100000000u && aiueos_apic_timer_ticks == 0; budget++)
    __asm__ volatile("pause");
  __asm__ volatile("cli");
  return aiueos_apic_timer_ticks != 0;
}

/* GRUB path: the same image is loaded by GRUB's `multiboot2` command, which
 * enters with the MB2 magic and a tag-list information structure. This is a
 * narrower landing than the QEMU-direct MB1 path — it proves GRUB boots the
 * kernel end-to-end (long mode, SSE, a bounded MB2 memory-map tag walk, and
 * the compiler-emitted Kotoba probe) and reaches the same ACPI + Local APIC
 * timer evidence as the MB1 path, taking the RSDP from a Multiboot2 ACPI tag
 * instead of a BIOS scan. */
__attribute__((noreturn))
static void multiboot2_landing(uint32_t info_addr) {
  const uint8_t *info = (const uint8_t *)(uintptr_t)info_addr;
  uint32_t total = *(const uint32_t *)(const void *)info;
  if (total < 8 || total > (1u << 20)) {
    serial_string("AIUEOS_MULTIBOOT2_FAIL info-size\r\n");
    qemu_exit(0x7d);
  }
  uint32_t offset = 8, usable = 0;
  const void *rsdp = 0;
  uint64_t fb_addr = 0; uint32_t fb_pitch = 0, fb_width = 0, fb_height = 0; uint8_t fb_bpp = 0;
  while (offset + 8 <= total) {
    const uint8_t *tag = info + offset;
    uint32_t type = *(const uint32_t *)(const void *)tag;
    uint32_t size = *(const uint32_t *)(const void *)(tag + 4);
    if (size < 8 || offset + size > total) {
      serial_string("AIUEOS_MULTIBOOT2_FAIL tag-size\r\n");
      qemu_exit(0x7c);
    }
    if (type == MULTIBOOT2_TAG_END) break;
    if (type == MULTIBOOT2_TAG_MMAP) {
      uint32_t entry_size = *(const uint32_t *)(const void *)(tag + 8);
      if (entry_size >= 24 && entry_size <= 4096) {
        for (uint32_t e = 16; e + entry_size <= size; e += entry_size) {
          const uint8_t *m = tag + e;
          uint64_t len = *(const uint64_t *)(const void *)(m + 8);
          uint32_t mtype = *(const uint32_t *)(const void *)(m + 16);
          if (mtype == 1 && len) usable++;
        }
      }
    } else if (type == MULTIBOOT2_TAG_ACPI_NEW && size >= 8 + 36) {
      rsdp = tag + 8;  /* ACPI 2.0 RSDP: prefer it (XSDT) */
    } else if (type == MULTIBOOT2_TAG_ACPI_OLD && size >= 8 + 20 && !rsdp) {
      rsdp = tag + 8;  /* ACPI 1.0 RSDP copy */
    } else if (type == MULTIBOOT2_TAG_FRAMEBUFFER && size >= 8 + 22) {
      fb_addr = *(const uint64_t *)(const void *)(tag + 8);
      fb_pitch = *(const uint32_t *)(const void *)(tag + 16);
      fb_width = *(const uint32_t *)(const void *)(tag + 20);
      fb_height = *(const uint32_t *)(const void *)(tag + 24);
      fb_bpp = tag[28];
      /* framebuffer type at tag[29]: 1 = direct RGB, which is all we drive */
      if (tag[29] != 1) fb_addr = 0;
    }
    offset += (size + 7) & ~7u;  /* tags are 8-byte aligned */
  }
  if (!usable) {
    serial_string("AIUEOS_MULTIBOOT2_FAIL no-usable-memory\r\n");
    qemu_exit(0x7b);
  }
  debug_string("AIUEOS_MULTIBOOT2_MMAP_OK\n");
  serial_string("AIUEOS_MULTIBOOT2_MMAP_OK tag-walk usable-region\r\n");

  /* Full evidence parity with the MB1 path: the RSDP arrives in a Multiboot2
   * ACPI tag (no BIOS scan), then the same ACPI parser, IDT, and Local APIC
   * timer as the QEMU-direct path. */
  if (!rsdp || !aiueos_acpi_initialize(rsdp) || aiueos_acpi_cpu_count() < 2) {
    serial_string("AIUEOS_MULTIBOOT2_FAIL acpi-validation\r\n");
    qemu_exit(0x6e);
  }
  debug_string("AIUEOS_MULTIBOOT2_ACPI_OK\n");
  serial_string("AIUEOS_MULTIBOOT2_ACPI_OK tag-rsdp madt cpu>=2 ioapic\r\n");
  if (!install_idt_and_time_lapic()) {
    serial_string("AIUEOS_MULTIBOOT2_FAIL apic-timer\r\n");
    qemu_exit(0x6c);
  }
  debug_string("AIUEOS_MULTIBOOT2_APIC_TIMER_OK\n");
  serial_string("AIUEOS_MULTIBOOT2_APIC_TIMER_OK idt lapic vector=32 eoi\r\n");

  /* GRUB set a linear framebuffer in response to the MB2 framebuffer request
   * tag (QEMU-direct MB1 has no framebuffer). Validate its geometry, write a
   * bounded test pattern, and require it to read back — proving the Multiboot
   * path can own a scanout surface, the GOP-equivalent the UEFI path drives. */
  /* Accept the direct-RGB modes GRUB provides on this firmware (24 or 32 bpp).
   * The test pattern is written and read byte-wise so both packings work. */
  uint32_t bytes_per_pixel = fb_bpp / 8u;
  if (!fb_addr || !fb_width || !fb_height || (fb_bpp != 24 && fb_bpp != 32) ||
      fb_pitch < fb_width * bytes_per_pixel) {
    serial_string("AIUEOS_MULTIBOOT2_FAIL framebuffer-geometry\r\n");
    qemu_exit(0x6b);
  }
  {
    volatile uint8_t *fb = (volatile uint8_t *)(uintptr_t)fb_addr;
    uint32_t rows = fb_height < 64u ? fb_height : 64u;
    uint32_t cols = fb_width < 64u ? fb_width : 64u;
    for (uint32_t y = 0; y < rows; y++)
      for (uint32_t x = 0; x < cols; x++) {
        uint64_t base = (uint64_t)y * fb_pitch + (uint64_t)x * bytes_per_pixel;
        uint8_t v = (uint8_t)(y * cols + x);
        for (uint32_t b = 0; b < bytes_per_pixel; b++)
          fb[base + b] = (uint8_t)(v + b * 0x33u);
      }
    uint32_t sum = 2166136261u, expect = 2166136261u;
    for (uint32_t y = 0; y < rows; y++)
      for (uint32_t x = 0; x < cols; x++) {
        uint64_t base = (uint64_t)y * fb_pitch + (uint64_t)x * bytes_per_pixel;
        uint8_t v = (uint8_t)(y * cols + x);
        for (uint32_t b = 0; b < bytes_per_pixel; b++) {
          sum = (sum ^ fb[base + b]) * 16777619u;
          expect = (expect ^ (uint8_t)(v + b * 0x33u)) * 16777619u;
        }
      }
    if (sum != expect) {
      serial_string("AIUEOS_MULTIBOOT2_FAIL framebuffer-readback\r\n");
      qemu_exit(0x6a);
    }
  }
  debug_string("AIUEOS_MULTIBOOT2_FRAMEBUFFER_OK\n");
  serial_string("AIUEOS_MULTIBOOT2_FRAMEBUFFER_OK grub-fb direct-rgb test-pattern readback\r\n");

  if (kotoba_aiueos_probe() != 42u) {
    serial_string("AIUEOS_MULTIBOOT2_FAIL kotoba-probe\r\n");
    qemu_exit(0x67);
  }
  debug_string("AIUEOS_MULTIBOOT2_OK\n");
  serial_string("AIUEOS_MULTIBOOT2_OK grub long-mode acpi apic-timer kotoba-probe=42\r\n");
  qemu_exit(0x2a);
}

void aiueos_multiboot_main(uint32_t magic, uint32_t info_addr) {
  serial_init();
  if (magic == MULTIBOOT2_BOOTLOADER_MAGIC) {
    debug_string("AIUEOS_MULTIBOOT2_ENTRY\n");
    multiboot2_landing(info_addr);
  }
  if (magic != MULTIBOOT_BOOTLOADER_MAGIC) {
    serial_string("AIUEOS_MULTIBOOT_FAIL magic\r\n");
    qemu_exit(0x7e);
  }
  const struct multiboot_info *info = (const struct multiboot_info *)(uintptr_t)info_addr;
  if (!(info->flags & MULTIBOOT_INFO_MMAP) || !info->mmap_length) {
    serial_string("AIUEOS_MULTIBOOT_FAIL mmap-absent\r\n");
    qemu_exit(0x7d);
  }
  /* Bounded walk of the variable-stride Multiboot memory map. Require at least
   * one usable (type 1) region and stay inside the advertised length. */
  uint32_t offset = 0, usable = 0;
  uint64_t usable_bytes = 0;
  while (offset + sizeof(struct multiboot_mmap_entry) <= info->mmap_length) {
    const struct multiboot_mmap_entry *entry =
      (const struct multiboot_mmap_entry *)(uintptr_t)(info->mmap_addr + offset);
    if (entry->size < 20 || entry->size > 4096) {
      serial_string("AIUEOS_MULTIBOOT_FAIL mmap-stride\r\n");
      qemu_exit(0x7c);
    }
    if (entry->type == 1 && entry->len) {
      usable++;
      usable_bytes += entry->len;
    }
    offset += entry->size + 4;  /* size field does not count itself */
  }
  if (!usable || usable_bytes < 0x100000ull) {
    serial_string("AIUEOS_MULTIBOOT_FAIL no-usable-memory\r\n");
    qemu_exit(0x7b);
  }
  debug_string("AIUEOS_MULTIBOOT_MMAP_OK\n");
  serial_string("AIUEOS_MULTIBOOT_MMAP_OK type1-regions bounded-walk\r\n");

  /* Firmware-independent ACPI RSDP discovery: no UEFI configuration table
   * hands the RSDP over on this path, so scan the BIOS window for a
   * signature- and checksum-valid Root System Description Pointer. Walking
   * the tables it references (an ACPI 1.0 RSDT here) reuses the kernel's
   * validated ACPI parser, which is currently ACPI-2.0/XSDT-only to match the
   * UEFI handoff; extending it to the RSDT is a follow-up. */
  const void *rsdp = find_rsdp();
  if (!rsdp) {
    serial_string("AIUEOS_MULTIBOOT_FAIL rsdp-absent\r\n");
    qemu_exit(0x6f);
  }
  debug_string("AIUEOS_MULTIBOOT_RSDP_OK\n");
  serial_string("AIUEOS_MULTIBOOT_RSDP_OK signature checksum firmware-independent\r\n");

  /* Walk the tables the RSDP references through the kernel's validated ACPI
   * parser (ACPI 1.0 RSDT here; the UEFI path uses the 2.0 XSDT). Require the
   * enumerated CPU count the parser's own >=2 SMP invariant guarantees. */
  if (!aiueos_acpi_initialize(rsdp) || aiueos_acpi_cpu_count() < 2) {
    serial_string("AIUEOS_MULTIBOOT_FAIL acpi-validation\r\n");
    qemu_exit(0x6e);
  }
  debug_string("AIUEOS_MULTIBOOT_ACPI_OK\n");
  serial_string("AIUEOS_MULTIBOOT_ACPI_OK rsdt-walk madt cpu>=2 ioapic\r\n");

  /* Interrupt handling on the Multiboot path: install a minimal IDT (all
   * vectors trap to a fail-fast default, vector 32 to the timer ISR), then
   * bring up the Local APIC periodic timer through the shared apic.c and wait
   * for a real hardware tick. The LAPIC MMIO at ~0xFEE00000 is reachable
   * because the trampoline now identity-maps the first 4 GiB. */
  if (!install_idt_and_time_lapic()) {
    serial_string("AIUEOS_MULTIBOOT_FAIL apic-timer\r\n");
    qemu_exit(0x6c);
  }
  debug_string("AIUEOS_MULTIBOOT_APIC_TIMER_OK\n");
  serial_string("AIUEOS_MULTIBOOT_APIC_TIMER_OK idt lapic vector=32 eoi\r\n");

  if (kotoba_aiueos_probe() != 42u) {
    serial_string("AIUEOS_MULTIBOOT_FAIL kotoba-probe\r\n");
    qemu_exit(0x67);
  }
  debug_string("AIUEOS_MULTIBOOT_KOTOBA_OK\n");
  serial_string("AIUEOS_MULTIBOOT_OK long-mode mmap-parsed kotoba-probe=42\r\n");
  /* isa-debug-exit maps value 0x2a to status (0x2a << 1) | 1 = 85. */
  qemu_exit(0x2a);
}
