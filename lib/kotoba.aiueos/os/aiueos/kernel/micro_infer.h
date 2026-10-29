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

/* The Kotoba decision (os/aiueos/kotoba/micro-infer-next.kotoba) writes the
   8-byte record straight into this struct: its C layout is the record's
   layout, so no C marshalling sits between them. Returns 1 on success. */
_Static_assert(sizeof(struct aiueos_micro_infer_result) ==
               AIUEOS_MICRO_INFER_RESULT_RECORD_BYTES, "result record size");
_Static_assert(__builtin_offsetof(struct aiueos_micro_infer_result, score) == 4 &&
               __builtin_offsetof(struct aiueos_micro_infer_result, total) == 6,
               "result record layout");
extern int64_t kotoba_aiueos_micro_infer_next(
  const uint8_t *prompt,int64_t length,uint8_t *out);

#endif
