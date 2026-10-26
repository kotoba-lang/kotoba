#ifndef AIUEOS_BOOT_INFO_H
#define AIUEOS_BOOT_INFO_H

#include <stdint.h>

#define AIUEOS_BOOT_INFO_MAGIC 0x414955454f53424fULL
#define AIUEOS_BOOT_INFO_VERSION_BASE 3ULL
#define AIUEOS_BOOT_INFO_VERSION_MODEL_HANDOFF 4ULL
#define AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED 5ULL

#define AIUEOS_MODEL_FORMAT_NONE 0U
#define AIUEOS_MODEL_FORMAT_GGUF 1U
#define AIUEOS_MODEL_HANDOFF_SHA256_VERIFIED (1ULL << 0)
#define AIUEOS_MODEL_HANDOFF_SPLIT_EXACT (1ULL << 1)
#define AIUEOS_MODEL_PAGING_PAGES 16U

/* Loader -> native-kernel ABI.  Additions are append-only: versions 2 and 3
 * end at firmware_cr3, while version 4 carries a read-only model allocation.
 * Version 5 fixes the paging aperture at AIUEOS_MODEL_PAGING_PAGES and reuses
 * the final v4 page-count word for calibrated tsc_hz. This keeps the handoff
 * and the kernel's early static layout byte-for-byte stable at 208 bytes.
 * The model bytes remain LoaderData after ExitBootServices and are mapped by
 * the kernel as supervisor-only, non-executable, read-only RAM. */
struct aiueos_boot_info {
  uint64_t magic, version;
  void *memory_map;
  uint64_t memory_map_size, descriptor_size, descriptor_version;
  void *acpi_rsdp;
  uint64_t framebuffer_base, framebuffer_size;
  uint32_t framebuffer_width, framebuffer_height;
  uint32_t framebuffer_stride, framebuffer_format;
  uint64_t initramfs_base, initramfs_size;
  void *runtime_services;
  uint64_t firmware_cr3;
  uint64_t model_base, model_size;
  uint8_t model_sha256[32];
  uint32_t model_part_count, model_format;
  uint64_t model_flags, model_load_cycles;
  uint64_t model_paging_base;
  union {
    uint64_t model_paging_pages; /* v4 */
    uint64_t tsc_hz;             /* v5, paging pages are fixed by the ABI */
  };
  /* v6 (G3, data encrypted at rest): the loader's data-disk key, carried to
     the kernel so the data disk can be written as ciphertext. The key lives
     on the system ESP (\EFI\AIUEOS\DATA.KEY), a different disk from the
     data volume it protects. data_key_tag != 0 means the fields are set. */
  uint8_t data_key[16];
  uint64_t data_key_tag;
};

_Static_assert(sizeof(struct aiueos_boot_info) == 232,
               "boot-info v3-v6 ABI size changed");

#endif
