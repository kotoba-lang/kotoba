/* The whole-plan contract of kotoba_aiueos_qwen35_matvec (arena, arena_bytes, 96-byte plan -> 0 or a refusal) over
   the native-route object's two exports (JUN-633): kotoba/qwen35-matvec.o answers the plan check
   (kotoba_aiueos_qwen35_matvec_check, every refusal -1 .. -11 the whole-tensor object made) and one row at a time
   (kotoba_aiueos_qwen35_matvec_row: the row's weights, the input and a scratch row, each a window of its own length,
   answering the row's dot product as f32 bits or a refusal below zero -- -12 when the row does not dequantise).
   The native route admits a window only with its owner's own length, so the row windows are cut here, from the
   plan the check has just admitted, and the loop over the plan's rows is this one. The arithmetic is the object's. */
#ifndef AIUEOS_QWEN35_MATVEC_PLAN_H
#define AIUEOS_QWEN35_MATVEC_PLAN_H
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_matvec_check(uint8_t *arena, uint64_t arena_bytes,
                                                 const uint8_t *plan, uint64_t plan_bytes);
extern int64_t kotoba_aiueos_qwen35_matvec_row(uint64_t type, const uint8_t *weights, uint64_t weights_bytes,
                                               const uint8_t *input, uint64_t input_bytes,
                                               uint8_t *scratch, uint64_t scratch_bytes);
static inline uint64_t qwen_matvec_plan_u64(const uint8_t *plan, uint32_t at) {
  uint64_t v = 0;
  for (uint32_t i = 0; i < 8; i++) v |= (uint64_t)plan[at + i] << (8 * i);
  return v;
}
static inline uint64_t qwen_matvec_kotoba(uint8_t *arena, uint64_t arena_bytes, const uint8_t *plan,
                                          uint64_t plan_bytes) {
  int64_t verdict = kotoba_aiueos_qwen35_matvec_check(arena, arena_bytes, plan, plan_bytes);
  if (verdict != 0) return (uint64_t)verdict;
  uint64_t type = qwen_matvec_plan_u64(plan, 0) & 0xffffffffULL;
  uint64_t rows = qwen_matvec_plan_u64(plan, 8), cols = qwen_matvec_plan_u64(plan, 16);
  uint64_t row_bytes = qwen_matvec_plan_u64(plan, 32) / rows;
  uint8_t *weights = arena + qwen_matvec_plan_u64(plan, 24), *input = arena + qwen_matvec_plan_u64(plan, 40);
  uint8_t *output = arena + qwen_matvec_plan_u64(plan, 48), *scratch = arena + qwen_matvec_plan_u64(plan, 56);
  uint64_t end = qwen_matvec_plan_u64(plan, 72);
  for (uint64_t row = qwen_matvec_plan_u64(plan, 64); row < end; row++) {
    int64_t bits = kotoba_aiueos_qwen35_matvec_row(type, weights + row * row_bytes, row_bytes,
                                                   input, cols * 4, scratch, cols * 4);
    if (bits < 0) return (uint64_t)bits;
    for (uint32_t i = 0; i < 4; i++) output[row * 4 + i] = (uint8_t)((uint64_t)bits >> (8 * i));
  }
  return 0;
}
#endif
