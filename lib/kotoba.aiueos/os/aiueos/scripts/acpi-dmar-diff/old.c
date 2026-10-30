/* kernel/acpi.c's parse_dmar before JUN-552 moved it to kotoba/acpi-dmar-parse.o, verbatim, with the SDT header and the
   four discovered_dmar globals it writes. */
#include <stdint.h>
#include <stddef.h>
#define PFX(x) old_##x
struct __attribute__((packed)) sdt_header {
  char signature[4]; uint32_t length; uint8_t revision, checksum;
  char oem_id[6], oem_table_id[8]; uint32_t oem_revision, creator_id, creator_revision;
};
static uint32_t discovered_dmar_drhd_count;
static uint64_t discovered_dmar_register_base;
static uint16_t discovered_dmar_segment;
static uint8_t discovered_dmar_include_all;
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

#include "epilogue.h"
