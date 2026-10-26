#include <stdint.h>

#define IA32_APIC_BASE_MSR 0x1b
#define APIC_GLOBAL_ENABLE (1ULL << 11)
#define APIC_BASE_MASK 0xfffff000ULL
#define EXPECTED_APIC_BASE 0xfee00000ULL

volatile uint64_t aiueos_apic_timer_ticks;
volatile uint32_t *aiueos_apic_mmio_base;

/* MSR access is mechanism and lives in kotoba/msr-read.kotoba and
   kotoba/msr-write.kotoba. It carries a decision with it: those objects admit
   only the five indices this kernel has a reason to touch -- IA32_APIC_BASE
   here, EFER and the SYSCALL block elsewhere -- and a refused index performs
   no rdmsr/wrmsr at all. The write reports 1 admitted / 0 refused; the read
   cannot signal refusal, because every 64-bit pattern is a legal MSR value, so
   0x1b's presence on the admitted list is what makes the read below sound. */
extern uint64_t kotoba_aiueos_msr_read(uint64_t index);
extern uint64_t kotoba_aiueos_msr_write(uint64_t index, uint64_t value);
static void write_register(uint32_t offset, uint32_t value) {
  aiueos_apic_mmio_base[offset / 4] = value;
  (void)aiueos_apic_mmio_base[0x20 / 4];
}
static uint32_t read_register(uint32_t offset) {
  return aiueos_apic_mmio_base[offset / 4];
}
void aiueos_apic_timer_mask(void) {
  write_register(0x320,read_register(0x320)|(1U<<16));
}
void aiueos_apic_timer_unmask(void) {
  write_register(0x320,read_register(0x320)&~(1U<<16));
}

int aiueos_apic_timer_initialize(void) {
  uint64_t base = kotoba_aiueos_msr_read(IA32_APIC_BASE_MSR);
  if ((base & APIC_BASE_MASK) != EXPECTED_APIC_BASE) return 0;
  if (!kotoba_aiueos_msr_write(IA32_APIC_BASE_MSR, base | APIC_GLOBAL_ENABLE))
    return 0;
  aiueos_apic_mmio_base = (volatile uint32_t *)(uintptr_t)EXPECTED_APIC_BASE;
  aiueos_apic_timer_ticks = 0;

  write_register(0xf0, (read_register(0xf0) & ~0xffU) | 0x100U | 0xffU);
  write_register(0x3e0, 0x3U);
  write_register(0x320, (1U << 17) | 32U);
  write_register(0x380, 100000U);
  return (read_register(0xf0) & 0x1ffU) == 0x1ffU &&
         (read_register(0x320) & 0x200ffU) == ((1U << 17) | 32U);
}
