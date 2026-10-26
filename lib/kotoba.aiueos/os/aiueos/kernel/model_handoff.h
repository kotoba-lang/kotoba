#ifndef AIUEOS_MODEL_HANDOFF_H
#define AIUEOS_MODEL_HANDOFF_H

#include <stdint.h>
#include "../include/boot_info.h"

#define AIUEOS_MODEL_IDENTITY_LIMIT (64ULL * 1024ULL * 1024ULL * 1024ULL)
#define AIUEOS_MODEL_RESERVED_APIC_START (3ULL * 1024ULL * 1024ULL * 1024ULL)
#define AIUEOS_MODEL_RESERVED_APIC_END (4ULL * 1024ULL * 1024ULL * 1024ULL)
#define AIUEOS_MODEL_MAX_PDPT_DIRECTORIES AIUEOS_MODEL_PAGING_PAGES
/* The flat records the Kotoba decisions read and write (ADR-0219); layouts
   in os/aiueos/kotoba/aiueos/model_mapping_plan.kotoba and
   os/aiueos/kotoba/model-handoff-validate.kotoba. */
#define AIUEOS_MODEL_MAPPING_PLAN_RECORD_BYTES 32U
#define AIUEOS_MODEL_HANDOFF_RECORD_BYTES 192U

struct aiueos_model_mapping_plan {
  uint64_t first_2m, last_2m;
  uint32_t first_pdpt, last_pdpt, directory_count;
};

int aiueos_model_mapping_plan(uint64_t base, uint64_t size,
                              struct aiueos_model_mapping_plan *plan);
void aiueos_model_handoff_pack(const struct aiueos_boot_info *boot,
                               uint64_t expected_size,
                               const uint8_t expected_sha256[32],
                               uint32_t expected_parts,
                               const uint8_t header[8],
                               uint8_t record[AIUEOS_MODEL_HANDOFF_RECORD_BYTES]);
int aiueos_model_handoff_validate(const struct aiueos_boot_info *boot,
                                  uint64_t expected_size,
                                  const uint8_t expected_sha256[32],
                                  uint32_t expected_parts,
                                  const uint8_t header[8]);
int aiueos_qwen38_model_handoff_admit(const struct aiueos_boot_info *boot);

#endif
