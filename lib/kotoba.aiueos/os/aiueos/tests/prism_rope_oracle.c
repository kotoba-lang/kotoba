/* The expected bytes of contracts/qwen35-rope-v1.edn (ADR-0222 stage B item 6,
 * the rope stage).
 *
 * The rotation is Prism llama.cpp's own CPU loop, PrismML-Eng/llama.cpp
 * 9a9394a895b96003ca842a6041cb28ac49a108f7, ggml/src/ggml-cpu/ops.cpp:
 * `ggml_rope_cache_init` (:5856) and `rotate_pairs` (:5944) as
 * `ggml_compute_forward_rope_flt` calls them for GGML_ROPE_TYPE_IMROPE with
 * freq_scale 1, ext_factor 0, attn_factor 1, no freq_factors and sin_sign 1.
 * For a text token the imrope sections [11 11 10 0] pick theta_t / theta_h /
 * theta_w, which all start at the same position and are all multiplied by the
 * same theta_scale, and the fourth section is empty, so the cache is the plain
 * NEOX one below (`ggml_mrope_cache_init` :5872 reduces to it).
 *
 * ONE SUBSTITUTION, AND IT IS THE POINT: `rope_yarn` calls `cosf` / `sinf`,
 * a host libm the kernel does not have. They are replaced by `bounded_cos` /
 * `bounded_sin` -- a transcription of `f64-cos-bounded` / `f64-sin-bounded`
 * from osaho's kotoba.kir (src/kotoba/kir.cljk:1280-1343 at 85ed11b): the same
 * binary64 constants, the same reduction, the same Horner order -- evaluated
 * on the binary32 angle widened exactly and rounded back to binary32. That is
 * what qwen35-rope.kotoba computes, so these bytes are the object's, and
 * `--measure` says how far they are from the host's cosf/sinf and from
 * binary64 libm over the object's whole admitted domain.
 *
 * Build with -ffp-contract=off: clang contracts `a*b - c*d` into an FMA by
 * default on arm64, and the object does not fuse.
 *
 *   cc -O2 -ffp-contract=off -o /tmp/prism_rope_oracle \
 *      os/aiueos/tests/prism_rope_oracle.c -lm
 *   /tmp/prism_rope_oracle            # the contract's vectors
 *   /tmp/prism_rope_oracle --measure  # disagreement counts
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define HEAD_DIM 256
#define N_DIMS 64
#define FREQ_BASE 10000000.0f

static double bits_f64(uint64_t b) { double d; memcpy(&d, &b, 8); return d; }
static uint32_t f32_bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

static double sin_quarter_turn(double v) {
  if (v == 0.0) return v;
  double z = v * v;
  double p = -7.647163731819816e-13 + z * 2.8114572543455206e-15;
  p = 1.6059043836821613e-10 + z * p;
  p = -2.505210838544172e-8 + z * p;
  p = 2.7557319223985893e-6 + z * p;
  p = -0.0001984126984126984 + z * p;
  p = 0.008333333333333333 + z * p;
  p = -0.16666666666666666 + z * p;
  return v + (v * z) * p;
}

static double cos_quarter_turn(double v) {
  double z = v * v;
  double p = -1.1470745597729725e-11 + z * 4.779477332387385e-14;
  p = 2.08767569878681e-9 + z * p;
  p = -2.755731922398589e-7 + z * p;
  p = 0.0000248015873015873 + z * p;
  p = -0.001388888888888889 + z * p;
  p = 0.041666666666666664 + z * p;
  p = -0.5 + z * p;
  return 1.0 + z * p;
}

/* `reduce-bounded-angle`. Only non-negative angles reach it (a position is
 * non-negative and theta_scale is positive), where round-half-away is
 * floor(x + 0.5). */
static void reduce(double v, double *reduced, int *quadrant) {
  double scaled = v * 0.6366197723675814;
  double nearest = floor(scaled + 0.5);
  *reduced = (v - nearest * 1.5707963267948966) - nearest * 6.123233995736766e-17;
  *quadrant = (int)((int64_t)nearest % 4);
}

static float bounded_sin(float theta) {
  double r; int q; reduce((double)theta, &r, &q);
  double s = q == 0 ? sin_quarter_turn(r) : q == 1 ? cos_quarter_turn(r)
           : q == 2 ? -sin_quarter_turn(r) : -cos_quarter_turn(r);
  return (float)s;
}

static float bounded_cos(float theta) {
  double r; int q; reduce((double)theta, &r, &q);
  double c = q == 0 ? cos_quarter_turn(r) : q == 1 ? -sin_quarter_turn(r)
           : q == 2 ? -cos_quarter_turn(r) : sin_quarter_turn(r);
  return (float)c;
}

/* ggml_rope_cache_init, the first N_DIMS entries (the rest are never read). */
static void cache_init(float theta_base, float theta_scale, float *cache) {
  float theta = theta_base;
  for (int i0 = 0; i0 < N_DIMS; i0 += 2) {
    float theta_interp = 1.0f * theta;
    cache[i0 + 0] = bounded_cos(theta_interp) * 1.0f;
    cache[i0 + 1] = bounded_sin(theta_interp) * 1.0f;
    cache[i0 + 1] *= 1.0f;
    theta *= theta_scale;
  }
}

/* rotate_pairs<float>(n_dims, n_dims/2, cache, src, dst), in place. */
static void rotate(float *head, const float *cache) {
  for (int i0 = 0; i0 < N_DIMS; i0 += 2) {
    const int ic = i0 / 2;
    const float cos_theta = cache[i0 + 0];
    const float sin_theta = cache[i0 + 1];
    const float x0 = head[ic];
    const float x1 = head[ic + N_DIMS / 2];
    head[ic] = x0 * cos_theta - x1 * sin_theta;
    head[ic + N_DIMS / 2] = x0 * sin_theta + x1 * cos_theta;
  }
}

static uint32_t lcg_state;
static float next_value(void) {
  lcg_state = lcg_state * 1664525u + 1013904223u;
  /* magnitudes 2^-6 .. 2^5, both signs: a spread of exponents, not mantissas */
  int e = (int)((lcg_state >> 24) % 12) - 6;
  float m = (float)((lcg_state >> 8) & 0xffff) / 65536.0f + 1.0f;
  float v = ldexpf(m, e);
  return (lcg_state & 1) ? -v : v;
}

static void hex(const float *v, int n) {
  for (int i = 0; i < n; i++) {
    uint32_t u = f32_bits(v[i]);
    printf("%02x%02x%02x%02x", u & 255, (u >> 8) & 255, (u >> 16) & 255, u >> 24);
  }
}

static void emit(const char *name, int heads, uint32_t position, uint32_t seed,
                 float theta_scale, int expose_pair0) {
  static float values[24 * HEAD_DIM];
  float cache[N_DIMS];
  lcg_state = seed;
  for (int i = 0; i < heads * HEAD_DIM; i++) values[i] = next_value();
  if (expose_pair0) {
    /* x0 = 0, x1 = 1: dimension 0 comes out as exactly -sin(theta_0) and
     * dimension 32 as exactly cos(theta_0), so a one-ulp change in either is
     * a changed byte instead of a rounding the rotation absorbs. */
    values[0] = 0.0f;
    values[N_DIMS / 2] = 1.0f;
  }
  printf("  {:name :%s, :heads %d, :position %u, :input-hex \"", name, heads, position);
  hex(values, heads * HEAD_DIM);
  cache_init((float)position, theta_scale, cache);
  for (int h = 0; h < heads; h++) rotate(values + h * HEAD_DIM, cache);
  printf("\", :expect-values-hex \"");
  hex(values, heads * HEAD_DIM);
  printf("\"}\n");
}

int main(int argc, char **argv) {
  const float theta_scale = powf(FREQ_BASE, -2.0f / N_DIMS);
  if (argc > 1 && !strcmp(argv[1], "--measure")) {
    const float from_double = (float)pow(10000000.0, -2.0 / 64.0);
    printf("theta_scale powf=0x%08x (float)pow=0x%08x\n",
           f32_bits(theta_scale), f32_bits(from_double));
    uint64_t angles = 0, vs_sinf = 0, vs_cosf = 0, vs_sin = 0, vs_cos = 0;
    for (uint32_t p = 0; p <= 25735; p++) {
      float theta = (float)p;
      for (int i = 0; i < N_DIMS / 2; i++) {
        float s = bounded_sin(theta), c = bounded_cos(theta);
        angles++;
        if (f32_bits(s) != f32_bits(sinf(theta))) vs_sinf++;
        if (f32_bits(c) != f32_bits(cosf(theta))) vs_cosf++;
        if (f32_bits(s) != f32_bits((float)sin((double)theta))) vs_sin++;
        if (f32_bits(c) != f32_bits((float)cos((double)theta))) vs_cos++;
        theta *= theta_scale;
      }
    }
    printf("angles=%llu sin!=sinf %llu cos!=cosf %llu sin!=(float)sin %llu cos!=(float)cos %llu\n",
           (unsigned long long)angles, (unsigned long long)vs_sinf,
           (unsigned long long)vs_cosf, (unsigned long long)vs_sin,
           (unsigned long long)vs_cos);
    return 0;
  }
  emit("position-zero", 1, 0, 11, theta_scale, 0);
  emit("position-one", 1, 1, 12, theta_scale, 0);
  emit("position-five-two-heads", 2, 5, 13, theta_scale, 0);
  emit("position-seven-key-heads", 4, 7, 14, theta_scale, 0);
  emit("position-six-query-heads", 24, 6, 15, theta_scale, 0);
  emit("position-4096", 1, 4096, 16, theta_scale, 0);
  emit("position-at-the-ceiling", 1, 25735, 17, theta_scale, 0);
  /* The first position whose pair-0 sine rounds differently when the low
   * part of pi/2 is dropped from the reduction, with pair 0's input set so
   * the sine reaches the output unrounded: without it no vector here tells a
   * one-part reduction from the intrinsic's two-part one (measured: with
   * random inputs at this position the rotation absorbed the ulp). */
  emit("position-15975-needs-the-low-part", 1, 15975, 18, theta_scale, 1);
  return 0;
}
