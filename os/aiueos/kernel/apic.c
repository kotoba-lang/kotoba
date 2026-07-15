#include <stdint.h>

#define IA32_APIC_BASE_MSR 0x1b
#define APIC_GLOBAL_ENABLE (1ULL << 11)
#define APIC_BASE_MASK 0xfffff000ULL
#define EXPECTED_APIC_BASE 0xfee00000ULL

volatile uint64_t aiueos_apic_timer_ticks;
volatile uint32_t *aiueos_apic_mmio_base;

static uint64_t read_msr(uint32_t msr) {
  uint32_t low, high;
  __asm__ volatile("rdmsr" : "=a"(low), "=d"(high) : "c"(msr));
  return ((uint64_t)high << 32) | low;
}
static void write_msr(uint32_t msr, uint64_t value) {
  __asm__ volatile("wrmsr" : : "c"(msr), "a"((uint32_t)value),
                   "d"((uint32_t)(value >> 32)));
}
static void write_register(uint32_t offset, uint32_t value) {
  aiueos_apic_mmio_base[offset / 4] = value;
  (void)aiueos_apic_mmio_base[0x20 / 4];
}
static uint32_t read_register(uint32_t offset) {
  return aiueos_apic_mmio_base[offset / 4];
}
int aiueos_apic_timer_initialize(void) {
  uint64_t base = read_msr(IA32_APIC_BASE_MSR);
  if ((base & APIC_BASE_MASK) != EXPECTED_APIC_BASE) return 0;
  write_msr(IA32_APIC_BASE_MSR, base | APIC_GLOBAL_ENABLE);
  aiueos_apic_mmio_base = (volatile uint32_t *)(uintptr_t)EXPECTED_APIC_BASE;
  aiueos_apic_timer_ticks = 0;

  write_register(0xf0, (read_register(0xf0) & ~0xffU) | 0x100U | 0xffU);
  write_register(0x3e0, 0x3U);
  write_register(0x320, (1U << 17) | 32U);
  write_register(0x380, 100000U);
  return (read_register(0xf0) & 0x1ffU) == 0x1ffU &&
         (read_register(0x320) & 0x200ffU) == ((1U << 17) | 32U);
}
