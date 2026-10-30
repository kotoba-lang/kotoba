/* The C select_output_token's selection loop was before JUN-554 moved it to kotoba/qwen35-select.o: verbatim from
   kernel/qwen35_infer.c (finite_float, struct qwen35_token_choice, the loop over one view, renamed old_select_view). */
#include <stdint.h>
struct qwen35_token_choice {
  uint32_t token;
  uint32_t second_token;
  float logit;
  float second_logit;
  uint64_t cycles;
  uint32_t failed_layer;
  uint32_t failure_stage;
};
static int finite_float(float value) {
  union { float value; uint32_t bits; } representation = {value};
  return (representation.bits & 0x7f800000U) != 0x7f800000U;
}
int old_select_view(const float *logits, uint32_t first, uint32_t count, struct qwen35_token_choice *choice) {
  for (uint32_t offset = 0; offset < count; offset++) {
    uint32_t token = first + offset;
    float logit = logits[offset];
    if (!finite_float(logit)) return 0;
    if (logit > choice->logit) {
      choice->second_logit = choice->logit;
      choice->second_token = choice->token;
      choice->logit = logit;
      choice->token = token;
    } else if (logit > choice->second_logit) {
      choice->second_logit = logit;
      choice->second_token = token;
    }
  }
  return 1;
}
