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
static uint32_t discovered_tpm2_seen, discovered_tpm2_present;
static uint32_t discovered_ivrs_seen;
static uint32_t discovered_ivrs_present;
static uint32_t discovered_ivrs_info;
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
/* SEEN and PRESENT are different questions and the pair is the diagnostic:
   seen=0 means the firmware described no AMD IOMMU at all, seen=1 present=0
   means it described one and we refused the table. Collapsing them would make
   "this machine has no IOMMU" and "this machine has one we could not read"
   look identical -- and the first is permission to run unisolated. */
uint32_t aiueos_acpi_tpm2_seen(void) { return discovered_tpm2_seen; }
uint32_t aiueos_acpi_tpm2_present(void) { return discovered_tpm2_present; }
uint32_t aiueos_acpi_ivrs_seen(void) { return discovered_ivrs_seen; }
uint32_t aiueos_acpi_ivrs_present(void) { return discovered_ivrs_present; }
/* IVinfo, the dword at offset 36. Reported rather than acted on: it carries the
   physical and virtual address sizes an AMD-Vi device table has to agree with,
   so it is the first field a parser will need and the first one worth proving
   we can read. */
uint32_t aiueos_acpi_ivrs_info(void) { return discovered_ivrs_info; }
uint64_t aiueos_acpi_dmar_register_base(void) { return discovered_dmar_register_base; }
uint16_t aiueos_acpi_dmar_segment(void) { return discovered_dmar_segment; }
int aiueos_acpi_dmar_include_all(void) { return discovered_dmar_include_all; }
void aiueos_acpi_set_vtd_translation_enabled(int enabled) { vtd_translation_enabled = enabled; }

/* An ACPI table is firmware-supplied input this kernel otherwise takes on
   trust, so whether its bytes are admissible is a decision and lives in
   kotoba/acpi-checksum-ok.kotoba and kotoba/acpi-table-valid.kotoba. What
   stays here is mechanism: reading a field in order to hand it to the
   decision, and dispatching on which known table this is.

   The two objects are separate because a kernel object exports exactly one
   symbol and cannot call another, and because their fuel tiers differ -- the
   checksum walks the table (4096) and the header check reads eight bytes
   (1024). `valid_sdt` composes them; neither decides anything on its own. */
extern uint64_t kotoba_aiueos_acpi_checksum_ok(uint64_t table, uint64_t length);
extern uint64_t kotoba_aiueos_acpi_table_valid(uint64_t table, uint64_t length,
                                               uint64_t expected_signature,
                                               uint64_t max_length);

/* Big-endian, first byte most significant, which is how the object reads the
   four leading bytes and how the ACPI tables are spelled in prose. */
#define ACPI_SIGNATURE_XSDT 0x58534454ULL /* 'X','S','D','T' */
#define ACPI_SIGNATURE_RSDT 0x52534454ULL /* 'R','S','D','T' */
#define ACPI_SIGNATURE_APIC 0x41504943ULL /* 'A','P','I','C' */
#define ACPI_SIGNATURE_DMAR 0x444d4152ULL /* 'D','M','A','R' */
/* AMD's counterpart to DMAR. The K16 is an AMD Ryzen 7 7735HS, so on the
   machine this OS is built for, DMAR is the table that is absent and IVRS is
   the one that is there -- every VT-d capability this tree proves is proved
   against silicon the board does not have. Discovery first: parsing IVHD
   entries and programming a device table is the next step and is not this one. */
#define ACPI_SIGNATURE_IVRS 0x49565253ULL /* 'I','V','R','S' */
/* The TPM 2.0 ACPI table, which is how firmware describes a hardware root of
   trust. Discovery before anything else, for the reason IVRS taught: a parser
   written against a table no run can produce is written blind. */
#define ACPI_SIGNATURE_TPM2 0x54504d32ULL /* 'T','P','M','2' */

static int bytes_equal(const char *a, const char *b, uint64_t count) {
  while (count--) if (*a++ != *b++) return 0; return 1;
}
static int checksum_ok(const void *table, uint32_t length) {
  return kotoba_aiueos_acpi_checksum_ok((uint64_t)(uintptr_t)table, length) != 0;
}
static int bounded_address(uint64_t address, uint32_t length) {
  return address != 0 && length != 0 && address < BOOTSTRAP_IDENTITY_LIMIT &&
         length <= ACPI_MAX_TABLE_SIZE && address <= BOOTSTRAP_IDENTITY_LIMIT - length;
}
/* The leading `bounded_address` is what makes reading `header->length` on the
   next line legal; the object re-derives that field from the table itself and
   refuses the table unless the two agree, so a truncating or mis-offset read
   here becomes a rejection rather than a shorter checksum over a longer
   table. */
static int valid_sdt(const struct sdt_header *header, uint64_t signature) {
  uint64_t address = (uint64_t)(uintptr_t)header;
  return bounded_address(address, sizeof(*header)) &&
         kotoba_aiueos_acpi_table_valid(address, header->length, signature,
                                        ACPI_MAX_TABLE_SIZE) != 0 &&
         checksum_ok(header, header->length);
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
  if (!bounded_address((uint64_t)(uintptr_t)rsdp, 20) ||
      !bytes_equal(rsdp->signature, "RSD PTR ", 8) || !checksum_ok(rsdp, 20)) return 0;
  /* ACPI 2.0+ (UEFI handoff) walks the 64-bit XSDT; ACPI 1.0 (the RSDP a
     firmware-less Multiboot boot finds in the BIOS window) walks the 32-bit
     RSDT. The entry pointer width is the only difference; the table discovery
     and MADT walk below are shared. */
  const struct sdt_header *root;
  uint32_t entry_width;
  if (rsdp->revision >= 2) {
    if (!bounded_address((uint64_t)(uintptr_t)rsdp, sizeof(*rsdp)) ||
        rsdp->length < sizeof(*rsdp) || rsdp->length > 4096 ||
        !checksum_ok(rsdp, rsdp->length)) return 0;
    root = (const void *)(uintptr_t)rsdp->xsdt_address;
    /* The signature comparison that used to sit beside this call is now one of
       the object's own clauses, so it is not repeated here. */
    if (!valid_sdt(root, ACPI_SIGNATURE_XSDT)) return 0;
    entry_width = 8;
  } else {
    root = (const void *)(uintptr_t)rsdp->rsdt_address;
    if (!valid_sdt(root, ACPI_SIGNATURE_RSDT)) return 0;
    entry_width = 4;
  }
  if ((root->length - sizeof(*root)) % entry_width != 0) return 0;

  uint32_t entries = (root->length - sizeof(*root)) / entry_width;
  const uint8_t *entry_bytes = (const uint8_t *)root + sizeof(*root);
  const struct madt_header *madt = 0;
  const struct sdt_header *dmar = 0;
  for (uint32_t i = 0; i < entries; i++) {
    uint64_t table_address = entry_width == 8
      ? *(const uint64_t *)(const void *)(entry_bytes + (uint64_t)i * 8)
      : *(const uint32_t *)(const void *)(entry_bytes + (uint64_t)i * 4);
    const struct sdt_header *candidate = (const void *)(uintptr_t)table_address;
    if (!bounded_address(table_address, sizeof(*candidate))) return 0;
    /* `bytes_equal` stays here as DISPATCH -- which of the two tables this
       kernel knows about is this? -- and is deliberately not the admission.
       The object re-derives the signature from the table's own bytes, so a
       dispatch that read the wrong offset or width cannot admit a table under
       a name it does not carry. Keeping the two apart is also what preserves
       the failure semantics below: a candidate that CLAIMS to be APIC or DMAR
       and then fails validation is a hard failure, where a merged
       dispatch-and-admit could only skip it -- and a skipped DMAR would leave
       `discovered_dmar_drhd_count` at 0, which is the input to
       `aiueos_dma_test_policy_allows_unisolated`. */
    if (bytes_equal(candidate->signature, "APIC", 4)) {
      if (!valid_sdt(candidate, ACPI_SIGNATURE_APIC) ||
          candidate->length < sizeof(struct madt_header)) return 0;
      madt = (const struct madt_header *)candidate;
    } else if (bytes_equal(candidate->signature, "DMAR", 4)) {
      if (dmar || !valid_sdt(candidate, ACPI_SIGNATURE_DMAR)) return 0;
      dmar = candidate;
    } else if (bytes_equal(candidate->signature, "TPM2", 4)) {
      /* Same fail-closed shape as DMAR and IVRS: a table that CLAIMS to
         describe a root of trust and does not validate must stop the boot. A
         skipped one leaves present at 0, which is indistinguishable from a
         machine with no TPM -- and "no TPM" is what a policy would read as
         permission to proceed without one. */
      discovered_tpm2_seen = 1;
      if (discovered_tpm2_present || !valid_sdt(candidate, ACPI_SIGNATURE_TPM2)) return 0;
      discovered_tpm2_present = 1;
    } else if (bytes_equal(candidate->signature, "IVRS", 4)) {
      /* Same fail-closed shape as DMAR above, and for the same reason: a table
         that CLAIMS to be IVRS and does not validate must stop the boot, not be
         skipped. Skipping would leave `discovered_ivrs_present` at 0, which is
         indistinguishable from a machine that has no IOMMU -- and that is
         exactly the state the DMA policy treats as permission to run
         unisolated. A malformed table must never buy that permission. */
      discovered_ivrs_seen = 1;
      if (discovered_ivrs_present || !valid_sdt(candidate, ACPI_SIGNATURE_IVRS) ||
          candidate->length < 48) return 0;
      discovered_ivrs_present = 1;
      discovered_ivrs_info =
          *(const uint32_t *)(const void *)((const uint8_t *)candidate + 36);
    }
  }
  if (!madt) return 0;
  if (dmar && !parse_dmar(dmar)) return 0;

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
