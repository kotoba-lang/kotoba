#include <stdint.h>
#include <stddef.h>

#define AP_TRAMPOLINE 0x8000U
#define APIC_ID 0x20U
#define APIC_ICR_LOW 0x300U
#define APIC_ICR_HIGH 0x310U

extern const uint8_t aiueos_ap_trampoline_start[], aiueos_ap_trampoline_end[];
extern const uint64_t aiueos_ap_trampoline_cr3, aiueos_ap_trampoline_entry;
extern const uint64_t aiueos_ap_trampoline_stack;
extern volatile uint32_t *aiueos_apic_mmio_base;
extern uint32_t aiueos_acpi_cpu_count(void);
extern uint32_t aiueos_acpi_apic_id(uint32_t index);
extern int aiueos_paging_seal_ap_trampoline(void);

static uint8_t ap_stack[65536] __attribute__((aligned(4096)));
static volatile uint32_t ap_online;
static volatile uint32_t ap_observed_id;

static void pause_loop(uint32_t count) {
  while (count--) __asm__ volatile("pause");
}
static void apic_write(uint32_t offset, uint32_t value) {
  aiueos_apic_mmio_base[offset / 4] = value;
  (void)aiueos_apic_mmio_base[APIC_ID / 4];
}
static int wait_icr(void) {
  for (uint32_t i = 0; i < 10000000U; i++) {
    if (!(aiueos_apic_mmio_base[APIC_ICR_LOW / 4] & (1U << 12))) return 1;
    __asm__ volatile("pause");
  }
  return 0;
}
static void patch64(uint8_t *copy, const uint64_t *symbol, uint64_t value) {
  uintptr_t offset = (uintptr_t)symbol - (uintptr_t)aiueos_ap_trampoline_start;
  *(uint64_t *)(void *)(copy + offset) = value;
}

__attribute__((noreturn)) void aiueos_ap_entry(void) {
  uint32_t id = aiueos_apic_mmio_base[APIC_ID / 4] >> 24;
  ap_observed_id = id;
  __atomic_store_n(&ap_online, 1, __ATOMIC_RELEASE);
  __asm__ volatile("outb %0, $0xe9" : : "a"((uint8_t)'A'));
  for (;;) __asm__ volatile("cli; hlt");
}

int aiueos_smp_start_application_processor(void) {
  if (aiueos_acpi_cpu_count() < 2 || !aiueos_apic_mmio_base) return 0;
  uint32_t bsp = aiueos_apic_mmio_base[APIC_ID / 4] >> 24;
  uint32_t target = 0xffffffffU;
  for (uint32_t i = 0; i < aiueos_acpi_cpu_count(); i++) {
    uint32_t id = aiueos_acpi_apic_id(i);
    if (id != bsp) { target = id; break; }
  }
  if (target == 0xffffffffU || target > 255U) return 0;
  size_t size = (size_t)(aiueos_ap_trampoline_end-aiueos_ap_trampoline_start);
  if (size > 4096) return 0;
  uint8_t *copy = (uint8_t *)(uintptr_t)AP_TRAMPOLINE;
  for (size_t i = 0; i < size; i++) copy[i] = aiueos_ap_trampoline_start[i];
  uint64_t cr3; __asm__ volatile("mov %%cr3, %0" : "=r"(cr3));
  patch64(copy, &aiueos_ap_trampoline_cr3, cr3);
  patch64(copy, &aiueos_ap_trampoline_entry, (uint64_t)(uintptr_t)aiueos_ap_entry);
  patch64(copy, &aiueos_ap_trampoline_stack,
          (uint64_t)(uintptr_t)(ap_stack + sizeof(ap_stack)));
  if (!aiueos_paging_seal_ap_trampoline()) return 0;
  ap_online = 0;
  apic_write(APIC_ICR_HIGH, target << 24);
  apic_write(APIC_ICR_LOW, 0x0000c500U);
  if (!wait_icr()) return 0;
  pause_loop(1000000);
  apic_write(APIC_ICR_HIGH, target << 24);
  apic_write(APIC_ICR_LOW, 0x00008500U);
  if (!wait_icr()) return 0;
  pause_loop(1000000);
  for (int attempt = 0; attempt < 2; attempt++) {
    apic_write(APIC_ICR_HIGH, target << 24);
    apic_write(APIC_ICR_LOW, 0x00000608U);
    if (!wait_icr()) return 0;
    pause_loop(2000000);
    if (__atomic_load_n(&ap_online, __ATOMIC_ACQUIRE)) break;
  }
  return ap_online && ap_observed_id == target;
}
