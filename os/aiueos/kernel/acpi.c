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

uint32_t aiueos_acpi_cpu_count(void) { return discovered_cpu_count; }
uint32_t aiueos_acpi_apic_id(uint32_t index) {
  return index < discovered_cpu_count ? discovered_apic_ids[index] : 0xffffffffU;
}

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

int aiueos_acpi_initialize(const void *rsdp_pointer) {
  discovered_cpu_count = 0;
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
  for (uint32_t i = 0; i < entries; i++) {
    const struct sdt_header *candidate = (const void *)(uintptr_t)addresses[i];
    if (!bounded_address(addresses[i], sizeof(*candidate))) return 0;
    if (bytes_equal(candidate->signature, "APIC", 4)) {
      if (!valid_sdt(candidate) || candidate->length < sizeof(struct madt_header)) return 0;
      madt = (const struct madt_header *)candidate;
      break;
    }
  }
  if (!madt) return 0;

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
    }
    cursor += length;
  }
  return enabled_cpus >= 2;
}
