#include <stdint.h>

extern uint32_t aiueos_acpi_ioapic_address(void);
extern uint32_t aiueos_acpi_ioapic_gsi_base(void);
extern uint32_t aiueos_acpi_timer_gsi(void);
extern uint32_t aiueos_acpi_apic_id(uint32_t index);

volatile uint64_t aiueos_external_timer_ticks;

static inline void out8(uint16_t port, uint8_t value) {
  __asm__ volatile("outb %0, %1" : : "a"(value), "Nd"(port));
}
static uint32_t ioapic_read(volatile uint32_t *base, uint8_t reg) {
  base[0] = reg; return base[4];
}
static void ioapic_write(volatile uint32_t *base, uint8_t reg, uint32_t value) {
  base[0] = reg; base[4] = value; (void)base[4];
}

int aiueos_ioapic_route_legacy_timer(void) {
  uint32_t address = aiueos_acpi_ioapic_address();
  uint32_t base_gsi = aiueos_acpi_ioapic_gsi_base();
  uint32_t timer_gsi = aiueos_acpi_timer_gsi();
  uint32_t bsp_id = aiueos_acpi_apic_id(0);
  if (address != 0xfec00000U || timer_gsi < base_gsi || bsp_id > 255) return 0;
  volatile uint32_t *ioapic = (volatile uint32_t *)(uintptr_t)address;
  uint32_t max_entry = (ioapic_read(ioapic, 1) >> 16) & 0xffU;
  uint32_t index = timer_gsi - base_gsi;
  if (index > max_entry) return 0;

  out8(0x21, 0xff); out8(0xa1, 0xff);
  ioapic_write(ioapic, (uint8_t)(0x10 + index * 2 + 1), bsp_id << 24);
  ioapic_write(ioapic, (uint8_t)(0x10 + index * 2), 33U);
  aiueos_external_timer_ticks = 0;

  uint16_t divisor = 11932;
  out8(0x43, 0x36);
  out8(0x40, (uint8_t)divisor);
  out8(0x40, (uint8_t)(divisor >> 8));
  return (ioapic_read(ioapic, (uint8_t)(0x10 + index * 2)) & 0x100ffU) == 33U;
}
