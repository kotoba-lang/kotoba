/* The expectations of qwen35-norm-v1's mode-3 vectors: `linear_attention`'s
 * output norm, the loop as it stood in kernel/qwen35_infer.c before aiueos
 * ADR-0222 moved it into the norm object (now `linear_output_norm_c`, the
 * reference parity profile 2 compares against).  The gate multiply is not
 * here: the object's mode 3 is the norm alone, and the gate is the
 * activation object's mode 4, which has its own contract.
 *
 *   cc -std=c11 -O0 -ffp-contract=off -o /tmp/lon os/aiueos/tests/qwen35_linear_output_norm_oracle.c
 *   /tmp/lon > vectors.edn
 *
 * -ffp-contract=off is not optional: on AArch64 the default fuses
 * `a * b + c` into one fmadd, which rounds once where the kernel (x86_64
 * baseline, no FMA) rounds twice. Prints one EDN map per vector. */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define EPSILON 0.000001f
#define MAX_VALUES 128U

static uint32_t state;
static uint8_t next_byte(void) {
  uint32_t x = state;
  x ^= x << 13; x ^= x >> 17; x ^= x << 5;
  state = x;
  return (uint8_t)(x & 0xffU);
}
/* The parity self-test's spread of magnitudes (qwen_parity_value). */
static float next_value(void) {
  int32_t mantissa = (int32_t)next_byte() - 128;
  int32_t exponent = (int32_t)(next_byte() & 15U) - 7;
  float value = (float)mantissa;
  for (int32_t step = 0; step < exponent; step++) value *= 2.0f;
  for (int32_t step = exponent; step < 0; step++) value *= 0.5f;
  return value;
}

/* The C, verbatim in its arithmetic, less the gate. */
static void output_norm(float *values, uint32_t heads, uint32_t width,
                        const float *weights) {
  for (uint32_t head = 0; head < heads; head++) {
    float *vector = values + head * width;
    double sum = 0.0;
    for (uint32_t index = 0; index < width; index++)
      sum += (double)(vector[index] * vector[index]);
    float scale = 1.0f / sqrtf((float)(sum / (double)width) + EPSILON);
    for (uint32_t index = 0; index < width; index++)
      vector[index] = vector[index] * scale * weights[index];
  }
}

static void hex(const float *v, uint32_t n) {
  const uint8_t *b = (const uint8_t *)v;
  putchar('"');
  for (uint32_t i = 0; i < n * 4U; i++) printf("%02x", b[i]);
  putchar('"');
}

static float a[MAX_VALUES], w[MAX_VALUES], out[MAX_VALUES];

static void vector(const char *name, uint32_t heads, uint32_t width,
                   uint32_t seed, int overflow) {
  state = seed;
  for (uint32_t i = 0; i < heads * width; i++) a[i] = next_value();
  for (uint32_t i = 0; i < width; i++) w[i] = next_value();
  /* Head 0's first square overflows binary32.  The C takes the infinity
     into the sum, the scale is 0 and the head comes out as signed zeros;
     mode 2 would rescale it and a sum that SKIPS the square (mode 2's
     `sumsq`) would give a nonzero scale.  Head 1 is ordinary. */
  if (overflow) a[0] = 1180591620717411303424.0f; /* 2^70 */
  memcpy(out, a, sizeof a);
  output_norm(out, heads, width, w);
  printf("  {:name :%s, :mode 3, :heads %u, :width %u, :a-hex ", name, heads,
         width);
  hex(a, heads * width);
  printf(", :b-hex ");
  hex(w, width);
  printf(", :expect-a-hex ");
  hex(out, heads * width);
  printf("}\n");
}

int main(void) {
  vector("linear-output-norm-2x8", 2U, 8U, 0x5a5a5a5u, 0);
  vector("linear-output-norm-4x32", 4U, 32U, 0x0c0ffeeu, 0);
  vector("linear-output-norm-overflowing-square", 2U, 8U, 0x1234567u, 1);
  return 0;
}
