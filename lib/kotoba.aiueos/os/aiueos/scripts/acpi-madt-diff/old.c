/* The MADT walk of kernel/acpi.c's aiueos_acpi_initialize before JUN-552 moved it to kotoba/acpi-madt-parse.o, verbatim, as
   the tail of a function over the headers and the discovered globals it writes. */
#include <stdint.h>
#include <stddef.h>
#define PFX(x) old_##x
struct __attribute__((packed)) sdt_header {
  char signature[4]; uint32_t length; uint8_t revision, checksum;
  char oem_id[6], oem_table_id[8]; uint32_t oem_revision, creator_id, creator_revision;
};
struct __attribute__((packed)) madt_header {
  struct sdt_header sdt; uint32_t local_apic_address, flags;
};

static uint32_t discovered_apic_ids[256];
static uint32_t discovered_cpu_count;
static uint32_t discovered_ioapic_address;
static uint32_t discovered_ioapic_gsi_base;
static uint32_t discovered_timer_gsi;
static int PFX(walk)(const struct madt_header *madt) {
  const uint8_t *cursor = (const uint8_t *)madt + sizeof(*madt);
  const uint8_t *end = (const uint8_t *)madt + madt->sdt.length;
  uint32_t enabled_cpus = 0;
  uint32_t ioapic_addresses[16], ioapic_gsi_bases[16], ioapic_count = 0;
  while (cursor < end) {
    if ((uint64_t)(end - cursor) < 2) return 0;
    uint8_t type = cursor[0], length = cursor[1];
    if (length < 2 || (uint64_t)(end - cursor) < length) return 0;
    if (type == 0) {
      if (length < 8) return 0;
      uint32_t flags = *(const uint32_t *)(const void *)(cursor + 4);
      if ((flags & 3U) && discovered_cpu_count < 256) {
        discovered_apic_ids[discovered_cpu_count++] = cursor[3];
        enabled_cpus++;
      }
    } else if (type == 9) {
      if (length < 16) return 0;
      uint32_t flags = *(const uint32_t *)(const void *)(cursor + 8);
      if ((flags & 3U) && discovered_cpu_count < 256) {
        discovered_apic_ids[discovered_cpu_count++] =
          *(const uint32_t *)(const void *)(cursor + 4);
        enabled_cpus++;
      }
    } else if (type == 1) {
      if (length < 12 || ioapic_count >= 16) return 0;
      uint32_t address = *(const uint32_t *)(const void *)(cursor + 4);
      uint32_t gsi_base = *(const uint32_t *)(const void *)(cursor + 8);
      if (!address || (address & 4095U)) return 0;
      for (uint32_t i = 0; i < ioapic_count; i++)
        if (ioapic_gsi_bases[i] == gsi_base) return 0;
      ioapic_addresses[ioapic_count] = address;
      ioapic_gsi_bases[ioapic_count++] = gsi_base;
    } else if (type == 2) {
      if (length < 10) return 0;
      if (cursor[2] == 0 && cursor[3] == 0)
        discovered_timer_gsi = *(const uint32_t *)(const void *)(cursor + 4);
    }
    cursor += length;
  }
  /* A MADT may expose multiple IOAPICs. Route the legacy timer through the
     controller whose GSI range begins closest at or below the timer GSI;
     rejecting every second entry made otherwise-valid K16 firmware fail. */
  uint32_t selected_base = 0;
  int selected = 0;
  for (uint32_t i = 0; i < ioapic_count; i++) {
    if (ioapic_gsi_bases[i] <= discovered_timer_gsi &&
        (!selected || ioapic_gsi_bases[i] > selected_base)) {
      discovered_ioapic_address = ioapic_addresses[i];
      discovered_ioapic_gsi_base = ioapic_gsi_bases[i];
      selected_base = ioapic_gsi_bases[i];
      selected = 1;
    }
  }
  return enabled_cpus >= 2 && discovered_ioapic_address == 0xfec00000U;
}
#include "epilogue.h"
