#include <stdint.h>
#include "model_handoff.h"
#include "aiueos-model-identity.h"

/* MARSHALLING ONLY (ADR-0219). The two decisions this file held -- the huge
   page mapping plan and the handoff admission -- are
   `os/aiueos/kotoba/aiueos/model_mapping_plan.kotoba` and
   `os/aiueos/kotoba/model-handoff-validate.kotoba`. This file packs the
   boot-info struct, the expected identity and the model's first eight bytes
   into the flat record those objects read, and unpacks the plan they write.
   No comparison lives here. Record layouts are the objects' header comments;
   contracts/model-handoff-validate-v1.edn seeds records packed by the very
   function below, so a layout drift turns it red. */

extern int64_t kotoba_aiueos_model_mapping_plan(int64_t base, int64_t size,
                                                uint8_t *out);
extern int64_t kotoba_aiueos_model_handoff_validate(uint8_t *record,
                                                    int64_t length);

static void put_u32(uint8_t *at, uint32_t v) {
  at[0] = (uint8_t)v; at[1] = (uint8_t)(v >> 8);
  at[2] = (uint8_t)(v >> 16); at[3] = (uint8_t)(v >> 24);
}

static void put_u64(uint8_t *at, uint64_t v) {
  put_u32(at, (uint32_t)v); put_u32(at + 4, (uint32_t)(v >> 32));
}

static uint32_t get_u32(const uint8_t *at) {
  return (uint32_t)at[0] | ((uint32_t)at[1] << 8) | ((uint32_t)at[2] << 16) |
         ((uint32_t)at[3] << 24);
}

static uint64_t get_u64(const uint8_t *at) {
  return (uint64_t)get_u32(at) | ((uint64_t)get_u32(at + 4) << 32);
}

int aiueos_model_mapping_plan(uint64_t base, uint64_t size,
                              struct aiueos_model_mapping_plan *plan) {
  uint8_t out[AIUEOS_MODEL_MAPPING_PLAN_RECORD_BYTES];
  uint32_t i;
  if (!plan) return 0;
  for (i = 0; i < sizeof(out); i++) out[i] = 0;
  if (kotoba_aiueos_model_mapping_plan((int64_t)base, (int64_t)size, out) != 1)
    return 0;
  plan->first_2m = get_u64(out);
  plan->last_2m = get_u64(out + 8);
  plan->first_pdpt = get_u32(out + 16);
  plan->last_pdpt = get_u32(out + 20);
  plan->directory_count = get_u32(out + 24);
  return 1;
}

void aiueos_model_handoff_pack(const struct aiueos_boot_info *boot,
                               uint64_t expected_size,
                               const uint8_t expected_sha256[32],
                               uint32_t expected_parts,
                               const uint8_t header[8],
                               uint8_t record[AIUEOS_MODEL_HANDOFF_RECORD_BYTES]) {
  uint32_t i;
  for (i = 0; i < AIUEOS_MODEL_HANDOFF_RECORD_BYTES; i++) record[i] = 0;
  record[0] = boot ? 1 : 0;
  record[1] = header ? 1 : 0;
  put_u64(record + 72, expected_size);
  put_u32(record + 80, expected_parts);
  for (i = 0; i < 32; i++) record[120 + i] = expected_sha256[i];
  if (header) for (i = 0; i < 8; i++) record[152 + i] = header[i];
  if (!boot) return;
  put_u64(record + 8, boot->magic);
  put_u64(record + 16, boot->version);
  put_u64(record + 24, boot->model_base);
  put_u64(record + 32, boot->model_size);
  put_u32(record + 40, boot->model_part_count);
  put_u32(record + 44, boot->model_format);
  put_u64(record + 48, boot->model_flags);
  put_u64(record + 56, boot->model_paging_base);
  put_u64(record + 64, boot->model_paging_pages);
  for (i = 0; i < 32; i++) record[88 + i] = boot->model_sha256[i];
}

int aiueos_model_handoff_validate(const struct aiueos_boot_info *boot,
                                  uint64_t expected_size,
                                  const uint8_t expected_sha256[32],
                                  uint32_t expected_parts,
                                  const uint8_t header[8]) {
  static uint8_t record[AIUEOS_MODEL_HANDOFF_RECORD_BYTES];
  aiueos_model_handoff_pack(boot, expected_size, expected_sha256,
                            expected_parts, header, record);
  return kotoba_aiueos_model_handoff_validate(
             record, AIUEOS_MODEL_HANDOFF_RECORD_BYTES) == 1;
}

int aiueos_qwen38_model_handoff_admit(const struct aiueos_boot_info *boot) {
  /* Reading the model's first eight bytes through model_base is the one
     dereference here, and it is a copy, not a judgment. */
  const uint8_t *header = boot && boot->model_base ?
    (const uint8_t *)(uintptr_t)boot->model_base : 0;
  return aiueos_model_handoff_validate(
    boot, AIUEOS_MODEL_TOTAL_BYTES, aiueos_expected_model_sha256,
    AIUEOS_MODEL_PART_COUNT, header);
}
