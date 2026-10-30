/* The qwen35 residual add before JUN-554 moved it to kotoba/qwen35-residual.o: ffn's loop verbatim from
   kernel/qwen35_infer.c (main 38ef55b9; linear and full attention end with the same loop over `normalized`), as
   old_add. */
#include <stdint.h>
#define EMBED 5120U
void old_add(float *state, const float *scratch_b) {
  for (uint32_t index = 0; index < EMBED; index++) state[index] += scratch_b[index];
}
