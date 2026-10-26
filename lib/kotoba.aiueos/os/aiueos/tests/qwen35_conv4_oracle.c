/* The expectations of qwen35-activation-v1's conv4 vectors (modes 5 and 6):
 * `linear_attention`'s kernel-4 depthwise conv, the loop as it stood in
 * kernel/qwen35_infer.c before aiueos ADR-0222 moved it into the activation
 * object (now `conv4_c`, the reference parity profile 2 compares against).
 *
 *   cc -std=c11 -O0 -ffp-contract=off -o /tmp/conv4 os/aiueos/tests/qwen35_conv4_oracle.c
 *   /tmp/conv4 > vectors.edn
 *
 * -ffp-contract=off is not optional: on AArch64 the default fuses
 * `a * b + c` into one fmadd, which rounds once where the kernel (x86_64
 * baseline, no FMA) rounds twice. Prints one EDN map per vector. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COUNT 24U

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

/* The C, verbatim in its arithmetic: `position` selects mode 6. */
static void conv4(float *values, const float *kernel, float *history_base,
                  int position) {
  for (uint32_t channel = 0; channel < COUNT; channel++) {
    float current = values[channel];
    float mixed = current * kernel[channel * 4U + 3U];
    if (history_base) {
      float *history = history_base + (uint64_t)channel * 3U;
      if (position)
        mixed += history[0] * kernel[channel * 4U + 0U] +
                 history[1] * kernel[channel * 4U + 1U] +
                 history[2] * kernel[channel * 4U + 2U];
      history[0] = history[1];
      history[1] = history[2];
      history[2] = current;
    }
    values[channel] = mixed;
  }
}

static void hex(const float *v, uint32_t n) {
  const uint8_t *b = (const uint8_t *)v;
  putchar('"');
  for (uint32_t i = 0; i < n * 4U; i++) printf("%02x", b[i]);
  putchar('"');
}

static float a[COUNT], k[COUNT * 4U], h[COUNT * 3U];
static float a_out[COUNT], h_out[COUNT * 3U];

static void fill(uint32_t seed) {
  state = seed;
  for (uint32_t i = 0; i < COUNT; i++) a[i] = next_value();
  for (uint32_t i = 0; i < COUNT * 4U; i++) k[i] = next_value();
  for (uint32_t i = 0; i < COUNT * 3U; i++) h[i] = next_value();
  /* Channel 0 is the signed-zero probe: current 0, tap 3 = -1, an all-zero
     history. Mode 5 answers -0 (the product alone); mode 6 answers +0
     (-0 plus the history's +0). A port that folded mode 5 into mode 6
     with a zero history agrees on every other channel. */
  a[0] = 0.0f; k[3] = -1.0f; h[0] = 0.0f; h[1] = 0.0f; h[2] = 0.0f;
  /* Channel 1: a magnitude whose tap-3 product and history sum cancel to
     the last bit only in the C's association. */
  a[1] = 16777216.0f; k[7] = 1.0f;
  h[3] = 1.0f; k[4] = 1.0f; h[4] = -16777216.0f; k[5] = 1.0f;
  h[5] = 1.0f; k[6] = 1.0f;
}

static void vector(const char *name, uint32_t mode, int with_history,
                   uint32_t seed) {
  fill(seed);
  memcpy(a_out, a, sizeof a);
  memcpy(h_out, h, sizeof h);
  conv4(a_out, k, with_history ? h_out : 0, mode == 6U);
  printf("  {:name :%s, :mode %u, :count %u, :a-hex ", name, mode, COUNT);
  hex(a, COUNT);
  printf(", :b-hex ");
  hex(k, COUNT * 4U);
  if (with_history) {
    printf(", :h-hex ");
    hex(h, COUNT * 3U);
  } else {
    printf(", :h-base-override 0");
  }
  printf(", :expect-a-hex ");
  hex(a_out, COUNT);
  if (with_history) {
    printf(", :expect-h-hex ");
    hex(h_out, COUNT * 3U);
  }
  printf(", :expected 0}\n");
}

int main(void) {
  vector("conv4-next", 6U, 1, 0x3c3c3c3u);
  vector("conv4-first-with-history", 5U, 1, 0x3c3c3c3u);
  vector("conv4-first-without-history", 5U, 0, 0x3c3c3c3u);
  vector("conv4-next-second-seed", 6U, 1, 0x0badf00u);
  return 0;
}
