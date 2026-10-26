/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_MICRO_INFER_H
#define AIUEOS_MICRO_INFER_H

#include <stdint.h>

#define AIUEOS_MICRO_INFER_MODEL "aiueos-char-bigram-v1"
#define AIUEOS_MICRO_INFER_PROMPT_MAX 64U
/* The flat record the Kotoba decision writes (ADR-0220); layout in
   os/aiueos/kotoba/micro-infer-next.kotoba. */
#define AIUEOS_MICRO_INFER_RESULT_RECORD_BYTES 8U

struct aiueos_micro_infer_result {
  uint8_t token;
  uint8_t input_index;
  uint8_t output_index;
  uint16_t score;
  uint16_t total;
};

int aiueos_micro_infer_next(
  const uint8_t *prompt,uint32_t length,
  struct aiueos_micro_infer_result *result);

#endif
