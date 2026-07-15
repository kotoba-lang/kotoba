#include <stdint.h>
#include <stddef.h>

#define VTD_CAP 0x08
#define VTD_ECAP 0x10
#define VTD_GCMD 0x18
#define VTD_GSTS 0x1c
#define VTD_RTADDR 0x20
#define VTD_CCMD 0x28
#define VTD_GCMD_TE (1U << 31)
#define VTD_GCMD_SRTP (1U << 30)
#define VTD_GSTS_TES (1U << 31)
#define VTD_GSTS_RTPS (1U << 30)
#define VTD_TABLE_ADDRESS 0x000ffffffffff000ULL
#define VTD_READ 1ULL
#define VTD_WRITE 2ULL
#define VTD_LARGE_PAGE (1ULL << 7)
#define VTD_DOMAIN_BYTES (128ULL * 1024 * 1024)

extern void *aiueos_allocate_physical_page(void);
extern int aiueos_map_pci_mmio(uint64_t address, uint64_t length);
extern uint32_t aiueos_acpi_dmar_drhd_count(void);
extern uint64_t aiueos_acpi_dmar_register_base(void);
extern uint16_t aiueos_acpi_dmar_segment(void);
extern int aiueos_acpi_dmar_include_all(void);
extern void aiueos_acpi_set_vtd_translation_enabled(int enabled);

static volatile uint8_t *registers;
static uint64_t *root_table, *context_table, *sl_pml4, *sl_pdpt, *sl_pd;
static uint32_t vtd_error;
uint32_t aiueos_vtd_error(void) { return vtd_error; }

static uint32_t read32(uint32_t offset) {
  return *(volatile uint32_t *)(void *)(registers + offset);
}
static uint64_t read64(uint32_t offset) {
  return *(volatile uint64_t *)(void *)(registers + offset);
}
static void write32(uint32_t offset, uint32_t value) {
  *(volatile uint32_t *)(void *)(registers + offset) = value;
}
static void write64(uint32_t offset, uint64_t value) {
  *(volatile uint64_t *)(void *)(registers + offset) = value;
}
static int wait32(uint32_t offset, uint32_t mask, uint32_t expected) {
  for (uint32_t budget = 0; budget < 10000000U; budget++) {
    if ((read32(offset) & mask) == expected) return 1;
    __asm__ volatile("pause");
  }
  return 0;
}
static int wait64_clear(uint32_t offset, uint64_t mask) {
  for (uint32_t budget = 0; budget < 10000000U; budget++) {
    if (!(read64(offset) & mask)) return 1;
    __asm__ volatile("pause");
  }
  return 0;
}

int aiueos_vtd_initialize(void) {
  vtd_error = 1;
  aiueos_acpi_set_vtd_translation_enabled(0);
  if (!aiueos_acpi_dmar_drhd_count()) return 1;
  if (aiueos_acpi_dmar_drhd_count() != 1 || aiueos_acpi_dmar_segment() != 0) return 0;
  uint64_t base = aiueos_acpi_dmar_register_base();
  if (!base || !aiueos_map_pci_mmio(base, 4096)) return 0;
  registers = (volatile uint8_t *)(uintptr_t)base;
  uint32_t version = read32(0);
  uint64_t cap = read64(VTD_CAP), ecap = read64(VTD_ECAP);
  /* Legacy root/context format, 48-bit adjusted guest width, and 2 MiB leaves. */
  if (!version || !(cap & (1ULL << (8 + 2))) || !(cap & (1ULL << 34))) return 0;

  root_table = aiueos_allocate_physical_page();
  context_table = aiueos_allocate_physical_page();
  sl_pml4 = aiueos_allocate_physical_page();
  sl_pdpt = aiueos_allocate_physical_page();
  sl_pd = aiueos_allocate_physical_page();
  if (!root_table || !context_table || !sl_pml4 || !sl_pdpt || !sl_pd) { vtd_error = 2; return 0; }

  sl_pml4[0] = ((uint64_t)(uintptr_t)sl_pdpt & VTD_TABLE_ADDRESS) | VTD_READ | VTD_WRITE;
  sl_pdpt[0] = ((uint64_t)(uintptr_t)sl_pd & VTD_TABLE_ADDRESS) | VTD_READ | VTD_WRITE;
  for (uint64_t i = 0; i < VTD_DOMAIN_BYTES / (2 * 1024 * 1024); i++)
    sl_pd[i] = (i * 2 * 1024 * 1024) | VTD_READ | VTD_WRITE | VTD_LARGE_PAGE;
  /* One bounded domain covers every requester on QEMU's segment-0 bus 0. */
  for (uint32_t devfn = 0; devfn < 256; devfn++) {
    context_table[devfn * 2] = ((uint64_t)(uintptr_t)sl_pml4 & VTD_TABLE_ADDRESS) | 1;
    context_table[devfn * 2 + 1] = 2 | (1ULL << 8); /* AW=48-bit, domain id 1 */
  }
  root_table[0] = ((uint64_t)(uintptr_t)context_table & VTD_TABLE_ADDRESS) | 1;
  __asm__ volatile("mfence" ::: "memory");

  write64(VTD_RTADDR, (uint64_t)(uintptr_t)root_table & VTD_TABLE_ADDRESS);
  write32(VTD_GCMD, VTD_GCMD_SRTP);
  if (!wait32(VTD_GSTS, VTD_GSTS_RTPS, VTD_GSTS_RTPS)) { vtd_error = 3; return 0; }
  write64(VTD_CCMD, (1ULL << 63) | (1ULL << 61));
  if (!wait64_clear(VTD_CCMD, 1ULL << 63)) { vtd_error = 4; return 0; }
  uint32_t iotlb = (uint32_t)((ecap >> 8) & 0x3ffU) * 16U + 8U;
  if (iotlb < 8 || iotlb > 0xff8) { vtd_error = 5; return 0; }
  write64(iotlb, (1ULL << 63) | (1ULL << 60));
  if (!wait64_clear(iotlb, 1ULL << 63)) { vtd_error = 6; return 0; }
  write32(VTD_GCMD, VTD_GCMD_TE);
  if (!wait32(VTD_GSTS, VTD_GSTS_TES, VTD_GSTS_TES)) { vtd_error = 7; return 0; }
  aiueos_acpi_set_vtd_translation_enabled(1);
  return 1;
}

uint64_t aiueos_vtd_domain_bytes(void) { return VTD_DOMAIN_BYTES; }
int aiueos_vtd_translation_enabled(void) {
  return registers && (read32(VTD_GSTS) & VTD_GSTS_TES);
}
