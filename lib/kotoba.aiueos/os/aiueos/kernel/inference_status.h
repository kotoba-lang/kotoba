/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_INFERENCE_STATUS_H
#define AIUEOS_INFERENCE_STATUS_H

#include <stdint.h>

#define AIUEOS_INFERENCE_STATUS_ABI_VERSION 2U
#define AIUEOS_INFERENCE_STATUS_TEXT_MAX 32U
#define AIUEOS_INFERENCE_TOKEN_MAX 10000000U
#define AIUEOS_INFERENCE_UNMEASURED UINT64_MAX
/* The flat record the Kotoba decision reads (ADR-0219); layout in
   os/aiueos/kotoba/inference-status-valid.kotoba. */
#define AIUEOS_INFERENCE_STATUS_RECORD_BYTES 200U

enum aiueos_inference_phase {
  AIUEOS_INFERENCE_ADMISSION = 1,
  AIUEOS_INFERENCE_LOADING = 2,
  AIUEOS_INFERENCE_PREFILL = 3,
  AIUEOS_INFERENCE_DECODING = 4,
  AIUEOS_INFERENCE_COMPLETE = 5,
  AIUEOS_INFERENCE_BLOCKED = 6,
  AIUEOS_INFERENCE_ERROR = 7
};

/* Every duration is raw monotonic nanoseconds.  A caller which has only TSC
   cycles MUST leave the duration fields UNMEASURED and report compute_cycles;
   cycles are not silently converted using a nominal CPU clock. */
struct aiueos_inference_status {
  uint32_t abi_version;
  uint32_t byte_size;
  enum aiueos_inference_phase phase;
  const char *model;
  const char *quant;
  const char *detail;
  uint32_t prompt_tokens;
  uint32_t generated_tokens;
  /* Excludes the first generated token.  decode_ns covers exactly this many
     subsequent autoregressive tokens. */
  uint32_t decode_tokens;
  uint32_t target_tokens;
  uint64_t artifact_bytes;
  uint64_t resident_bytes;
  uint64_t load_ns;
  uint64_t prefill_ns;
  uint64_t decode_ns;
  uint64_t time_to_first_token_ns;
  uint64_t compute_cycles;
};

void aiueos_inference_status_pack(const struct aiueos_inference_status *status,
                                  uint8_t record[AIUEOS_INFERENCE_STATUS_RECORD_BYTES]);
int aiueos_inference_status_valid(const struct aiueos_inference_status *status);
uint64_t aiueos_inference_milli_tokens_per_second(uint32_t tokens,
                                                  uint64_t elapsed_ns);
int aiueos_framebuffer_inference_screen(
    const struct aiueos_inference_status *status);

#endif
