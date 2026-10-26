/* SPDX-License-Identifier: Apache-2.0 */
#include "micro_infer.h"

/* MARSHALLING ONLY (ADR-0220). The frozen character-bigram model and the
   decision over it are `os/aiueos/kotoba/micro-infer-next.kotoba` over the
   shared `native/micro_infer.kotoba` table -- the same module the
   pure-native kernel reduces with. The matrix's source of truth is
   contracts/micro-infer-transitions-v1.edn; it was this file's C array. What
   is left here unpacks the 8-byte result record into the caller's struct. */

extern int64_t kotoba_aiueos_micro_infer_next(const uint8_t *prompt,
                                              int64_t length, uint8_t *out);

int aiueos_micro_infer_next(
    const uint8_t *prompt,uint32_t length,
    struct aiueos_micro_infer_result *result) {
  uint8_t out[AIUEOS_MICRO_INFER_RESULT_RECORD_BYTES];
  uint32_t i;
  if (!prompt || !result) return 0;
  for (i = 0; i < sizeof(out); i++) out[i] = 0;
  if (kotoba_aiueos_micro_infer_next(prompt, (int64_t)length, out) != 1)
    return 0;
  result->token = out[0];
  result->input_index = out[1];
  result->output_index = out[2];
  result->score = (uint16_t)(out[4] | ((uint16_t)out[5] << 8));
  result->total = (uint16_t)(out[6] | ((uint16_t)out[7] << 8));
  return 1;
}
