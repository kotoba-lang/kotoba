#include <stdint.h>
#include <stddef.h>

#define ACPI_MAX_TABLE_SIZE (1024U * 1024U)
#define BOOTSTRAP_IDENTITY_LIMIT 0x40000000ULL

struct __attribute__((packed)) rsdp_v2 {
  char signature[8]; uint8_t checksum; char oem_id[6]; uint8_t revision;
  uint32_t rsdt_address, length; uint64_t xsdt_address;
  uint8_t extended_checksum, reserved[3];
};
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
static uint32_t discovered_dmar_drhd_count;
static uint64_t discovered_dmar_register_base;
static uint16_t discovered_dmar_segment;
static uint8_t discovered_dmar_include_all;
static int vtd_translation_enabled;

uint32_t aiueos_acpi_cpu_count(void) { return discovered_cpu_count; }
uint32_t aiueos_acpi_apic_id(uint32_t index) {
  return index < discovered_cpu_count ? discovered_apic_ids[index] : 0xffffffffU;
}
uint32_t aiueos_acpi_ioapic_address(void) { return discovered_ioapic_address; }
uint32_t aiueos_acpi_ioapic_gsi_base(void) { return discovered_ioapic_gsi_base; }
uint32_t aiueos_acpi_timer_gsi(void) { return discovered_timer_gsi; }
int aiueos_dma_test_policy_allows_unisolated(void) {
  return discovered_dmar_drhd_count == 0 || vtd_translation_enabled;
}
uint32_t aiueos_acpi_dmar_drhd_count(void) { return discovered_dmar_drhd_count; }
uint64_t aiueos_acpi_dmar_register_base(void) { return discovered_dmar_register_base; }
uint16_t aiueos_acpi_dmar_segment(void) { return discovered_dmar_segment; }
int aiueos_acpi_dmar_include_all(void) { return discovered_dmar_include_all; }
void aiueos_acpi_set_vtd_translation_enabled(int enabled) { vtd_translation_enabled = enabled; }

static int bytes_equal(const char *a, const char *b, uint64_t count) {
  while (count--) if (*a++ != *b++) return 0; return 1;
}
static int checksum_ok(const void *table, uint32_t length) {
  const uint8_t *bytes = table; uint8_t sum = 0;
  for (uint32_t i = 0; i < length; i++) sum = (uint8_t)(sum + bytes[i]);
  return sum == 0;
}
static int bounded_address(uint64_t address, uint32_t length) {
  return address != 0 && length != 0 && address < BOOTSTRAP_IDENTITY_LIMIT &&
         length <= ACPI_MAX_TABLE_SIZE && address <= BOOTSTRAP_IDENTITY_LIMIT - length;
}
static int valid_sdt(const struct sdt_header *header) {
  uint64_t address = (uint64_t)(uintptr_t)header;
  return bounded_address(address, sizeof(*header)) &&
         header->length >= sizeof(*header) &&
         bounded_address(address, header->length) && checksum_ok(header, header->length);
}

static int parse_dmar(const struct sdt_header *header) {
  if (header->length < sizeof(*header) + 12) return 0;
  const uint8_t *bytes = (const uint8_t *)header;
  uint8_t width = bytes[sizeof(*header)];
  if (width < 31 || width > 63) return 0;
  const uint8_t *cursor = bytes + sizeof(*header) + 12;
  const uint8_t *end = bytes + header->length;
  uint32_t drhds = 0;
  while (cursor < end) {
    if ((uint64_t)(end - cursor) < 4) return 0;
    uint16_t type = *(const uint16_t *)(const void *)cursor;
    uint16_t length = *(const uint16_t *)(const void *)(cursor + 2);
    if (length < 4 || (uint64_t)(end - cursor) < length) return 0;
    if (type == 0) {
      if (length < 16) return 0;
      uint64_t base = *(const uint64_t *)(const void *)(cursor + 8);
      uint16_t segment = *(const uint16_t *)(const void *)(cursor + 6);
      /* The register base is data, not dereferenced during discovery. Keep it
         page-aligned and within x86-64's architectural 52-bit physical range. */
      if (!base || (base & 4095) || base >= (1ULL << 52)) return 0;
      if (!discovered_dmar_register_base && segment == 0) {
        discovered_dmar_include_all = cursor[4] & 1;
        discovered_dmar_register_base = base;
        discovered_dmar_segment = segment;
      }
      const uint8_t *scope = cursor + 16;
      const uint8_t *scope_end = cursor + length;
      while (scope < scope_end) {
        if ((uint64_t)(scope_end - scope) < 6 || scope[1] < 6 ||
            (uint64_t)(scope_end - scope) < scope[1] || ((scope[1] - 6) & 1)) return 0;
        scope += scope[1];
      }
      drhds++;
    }
    cursor += length;
  }
  if (!drhds || !discovered_dmar_register_base) return 0;
  discovered_dmar_drhd_count = drhds;
  return 1;
}

int aiueos_acpi_initialize(const void *rsdp_pointer) {
  discovered_cpu_count = 0;
  discovered_ioapic_address = 0;
  discovered_ioapic_gsi_base = 0;
  discovered_timer_gsi = 0;
  discovered_dmar_drhd_count = 0;
  discovered_dmar_register_base = 0;
  discovered_dmar_segment = 0;
  discovered_dmar_include_all = 0;
  vtd_translation_enabled = 0;
  const struct rsdp_v2 *rsdp = rsdp_pointer;
  if (!bounded_address((uint64_t)(uintptr_t)rsdp, sizeof(*rsdp)) ||
      !bytes_equal(rsdp->signature, "RSD PTR ", 8) || rsdp->revision < 2 ||
      rsdp->length < sizeof(*rsdp) || rsdp->length > 4096 ||
      !checksum_ok(rsdp, 20) || !checksum_ok(rsdp, rsdp->length)) return 0;
  const struct sdt_header *xsdt = (const void *)(uintptr_t)rsdp->xsdt_address;
  if (!valid_sdt(xsdt) || !bytes_equal(xsdt->signature, "XSDT", 4) ||
      (xsdt->length - sizeof(*xsdt)) % 8 != 0) return 0;

  uint32_t entries = (xsdt->length - sizeof(*xsdt)) / 8;
  const uint64_t *addresses = (const void *)((const uint8_t *)xsdt + sizeof(*xsdt));
  const struct madt_header *madt = 0;
  const struct sdt_header *dmar = 0;
  for (uint32_t i = 0; i < entries; i++) {
    const struct sdt_header *candidate = (const void *)(uintptr_t)addresses[i];
    if (!bounded_address(addresses[i], sizeof(*candidate))) return 0;
    if (bytes_equal(candidate->signature, "APIC", 4)) {
      if (!valid_sdt(candidate) || candidate->length < sizeof(struct madt_header)) return 0;
      madt = (const struct madt_header *)candidate;
    } else if (bytes_equal(candidate->signature, "DMAR", 4)) {
      if (dmar || !valid_sdt(candidate)) return 0;
      dmar = candidate;
    }
  }
  if (!madt) return 0;
  if (dmar && !parse_dmar(dmar)) return 0;

  const uint8_t *cursor = (const uint8_t *)madt + sizeof(*madt);
  const uint8_t *end = (const uint8_t *)madt + madt->sdt.length;
  uint32_t enabled_cpus = 0;
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
      if (length < 12 || discovered_ioapic_address) return 0;
      discovered_ioapic_address = *(const uint32_t *)(const void *)(cursor + 4);
      discovered_ioapic_gsi_base = *(const uint32_t *)(const void *)(cursor + 8);
    } else if (type == 2) {
      if (length < 10) return 0;
      if (cursor[2] == 0 && cursor[3] == 0)
        discovered_timer_gsi = *(const uint32_t *)(const void *)(cursor + 4);
    }
    cursor += length;
  }
  return enabled_cpus >= 2 && discovered_ioapic_address == 0xfec00000U;
}
