#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "qwen35_infer.h"

#define HEAD 128U
#define FULL_HEAD 256U
#define FULL_KV 1024U

float aiueos_qwen35_test_softplus(float);
void aiueos_qwen35_test_rope(float[FULL_HEAD], uint32_t);
void aiueos_qwen35_test_recurrent_step(
    float[HEAD * HEAD], const float[HEAD], const float[HEAD],
    const float[HEAD], float, float, float[HEAD], float[HEAD]);
uint32_t aiueos_qwen35_test_linear_key_head(uint32_t);
int aiueos_qwen35_test_attention_score(
    const float[FULL_HEAD], const float[FULL_HEAD], double *);
uint64_t aiueos_qwen35_test_cache_hash(const float[FULL_KV]);
int aiueos_qwen35_test_cache_resolve(
    float[FULL_KV], float[FULL_KV], uint64_t);

int aiueos_qwen35_test_output_select(
    const struct aiueos_qwen35_tensor *, uint32_t, float *, float *, float *,
    uint32_t *, uint32_t *, float *, float *);

/* A synthetic quantisation type for the output-projection test: a row is 4
   bytes of seed and dequantises to EMBED values derived from it, so a vocab
   that spans three FFN-row views costs 139 KB and not 713 MB of F32. */
#define TEST_TYPE 0x7e57U
#define EMBED 5120U
#define FFN 17408U
#define VOCAB (2U * FFN + 3U)

static float synthetic_value(uint32_t seed, uint32_t index) {
  uint32_t x = seed * 2654435761U + index * 40503U + 1U;
  x ^= x << 13; x ^= x >> 17; x ^= x << 5;
  return (float)((int32_t)(x & 0xffffU) - 32768) / 65536.0f;
}

int aiueos_qwen35_dequantize_row(uint32_t type, const uint8_t *data,
                                 uint64_t elements, float *output) {
  if (type != TEST_TYPE || elements != EMBED) return 0;
  uint32_t seed;
  memcpy(&seed, data, 4);
  /* a seed with the top bit set is the INPUT scaled by its low bits, which
     is how the test plants a logit it knows will win */
  for (uint32_t i = 0; i < EMBED; i++)
    output[i] = (seed & 0x80000000U) ?
      synthetic_value(7U, i) * (float)(seed & 0xffU) :
      synthetic_value(seed, i);
  return 1;
}

uint64_t aiueos_qwen35_quant_row_bytes(uint32_t type, uint64_t elements) {
  return type == TEST_TYPE && elements == EMBED ? 4U : 0U;
}

/* dot_scalar's tree, which the host build's matvec reduces to */
static float reference_dot(const float *left, const float *right) {
  float s0 = 0.0f, s1 = 0.0f, s2 = 0.0f, s3 = 0.0f;
  for (uint32_t i = 0; i < EMBED; i += 4) {
    s0 += left[i] * right[i];
    s1 += left[i + 1] * right[i + 1];
    s2 += left[i + 2] * right[i + 2];
    s3 += left[i + 3] * right[i + 3];
  }
  return (s0 + s1) + (s2 + s3);
}

static uint32_t output_seeds[VOCAB];
static float output_input[EMBED], output_row[FFN], output_logits[FFN];
static float reference_row[EMBED];

static uint32_t float_bits(float value) {
  uint32_t bits;
  memcpy(&bits, &value, 4);
  return bits;
}

static int near(float actual, float expected, float tolerance) {
  return fabsf(actual - expected) <= tolerance;
}

#define CHECK(x) do { if (!(x)) { \
  fprintf(stderr, "check failed: %s\n", #x); return 1; \
} } while (0)

static float recurrent_state[HEAD * HEAD];
static float expected_state[HEAD * HEAD];
static float key[HEAD], query[HEAD], value[HEAD];
static float correction[HEAD], output[HEAD], expected_output[HEAD];
static float primary_cache[FULL_KV], shadow_cache[FULL_KV];

static void reference_step(float decay, float beta) {
  float reference_correction[HEAD];
  for (uint32_t column = 0; column < HEAD; column++) {
    float remembered = 0.0f;
    for (uint32_t row = 0; row < HEAD; row++) {
      expected_state[row * HEAD + column] *= decay;
      remembered += expected_state[row * HEAD + column] * key[row];
    }
    reference_correction[column] = (value[column] - remembered) * beta;
  }
  for (uint32_t row = 0; row < HEAD; row++)
    for (uint32_t column = 0; column < HEAD; column++)
      expected_state[row * HEAD + column] +=
        key[row] * reference_correction[column];
  for (uint32_t column = 0; column < HEAD; column++) {
    float sum = 0.0f;
    for (uint32_t row = 0; row < HEAD; row++)
      sum += expected_state[row * HEAD + column] * query[row];
    expected_output[column] = sum * 0.08838834764831845f;
  }
}

int main(void) {
  CHECK(strcmp(aiueos_qwen35_failure_stage_label(
                 AIUEOS_QWEN35_FAILURE_FULL_KEY), "FULL KEY") == 0);
  CHECK(strcmp(aiueos_qwen35_failure_stage_label(
                 AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX), "SOFTMAX") == 0);
  CHECK(strcmp(aiueos_qwen35_failure_stage_label(
                 AIUEOS_QWEN35_FAILURE_FULL_QUERY), "FULL QUERY") == 0);
  CHECK(strcmp(aiueos_qwen35_failure_stage_label(
                 AIUEOS_QWEN35_FAILURE_FULL_CACHE), "KV CACHE") == 0);
  CHECK(strcmp(aiueos_qwen35_failure_stage_label(999U), "UNKNOWN") == 0);

  /* Qwen3.5 repeat_interleave maps each of the 16 Q/K heads to three
     adjacent value heads, rather than cycling heads with modulo. */
  for (uint32_t head = 0; head < 48U; head++)
    CHECK(aiueos_qwen35_test_linear_key_head(head) == head / 3U);

  /* Finite full-attention operands are multiplied in double precision so
     their score cannot fail solely because a float product overflows. */
  float large_query[FULL_HEAD], large_key[FULL_HEAD];
  for (uint32_t i = 0; i < FULL_HEAD; i++) {
    large_query[i] = 1.0e30f;
    large_key[i] = i & 1U ? -1.0e30f : 1.0e30f;
  }
  double large_score = 0.0;
  CHECK(aiueos_qwen35_test_attention_score(
          large_query, large_key, &large_score));
  CHECK(isfinite(large_score));

  for (uint32_t i = 0; i < FULL_KV; i++)
    primary_cache[i] = shadow_cache[i] = (float)(i + 1U) / 1024.0f;
  uint64_t cache_hash = aiueos_qwen35_test_cache_hash(primary_cache);
  primary_cache[17] += 1.0f;
  CHECK(aiueos_qwen35_test_cache_resolve(
          primary_cache, shadow_cache, cache_hash));
  CHECK(memcmp(primary_cache, shadow_cache, sizeof(primary_cache)) == 0);
  primary_cache[17] += 1.0f;
  shadow_cache[18] += 1.0f;
  CHECK(!aiueos_qwen35_test_cache_resolve(
          primary_cache, shadow_cache, cache_hash));

  const float samples[] = {-10.0f, -1.0f, 0.0f, 1.0f, 10.0f};
  for (uint32_t i = 0; i < sizeof(samples) / sizeof(samples[0]); i++) {
    float expected = log1pf(expf(samples[i]));
    CHECK(near(aiueos_qwen35_test_softplus(samples[i]), expected, 0.00002f));
  }

  float rope[FULL_HEAD] = {0};
  rope[0] = 1.0f;
  aiueos_qwen35_test_rope(rope, 1);
  CHECK(near(rope[0], cosf(1.0f), 0.000002f));
  CHECK(near(rope[32], sinf(1.0f), 0.000002f));

  key[0] = 0.6f; key[1] = 0.8f;
  query[0] = 0.8f; query[1] = 0.6f;
  for (uint32_t i = 0; i < HEAD; i++) value[i] = (float)(i + 1U) / 256.0f;
  reference_step(1.0f, 0.25f);
  aiueos_qwen35_test_recurrent_step(
    recurrent_state, key, query, value, 1.0f, 0.25f,
    correction, output);
  for (uint32_t i = 0; i < HEAD * HEAD; i++)
    CHECK(near(recurrent_state[i], expected_state[i], 0.0000005f));
  for (uint32_t i = 0; i < HEAD; i++)
    CHECK(near(output[i], expected_output[i], 0.0000005f));

  for (uint32_t i = 0; i < HEAD; i++)
    value[i] = (float)(HEAD - i) / 128.0f;
  reference_step(0.75f, 0.4f);
  aiueos_qwen35_test_recurrent_step(
    recurrent_state, key, query, value, 0.75f, 0.4f,
    correction, output);
  for (uint32_t i = 0; i < HEAD * HEAD; i++)
    CHECK(near(recurrent_state[i], expected_state[i], 0.000001f));
  for (uint32_t i = 0; i < HEAD; i++)
    CHECK(near(output[i], expected_output[i], 0.000001f));

  /* The output projection over three views (FFN, FFN, 3 rows): the first
     and second choices are planted in the third and first views, and the reference is
     the per-row loop evaluate_token ran before it went through matvec. */
  for (uint32_t i = 0; i < EMBED; i++) output_input[i] = synthetic_value(7U, i);
  for (uint32_t row = 0; row < VOCAB; row++) output_seeds[row] = row + 11U;
  output_seeds[2U * FFN + 1U] = 0x80000003U;  /* winner, third view */
  output_seeds[4] = 0x80000002U;              /* runner-up, first view */
  {
    struct aiueos_qwen35_tensor tensor;
    memset(&tensor, 0, sizeof tensor);
    tensor.dimensions[0] = EMBED;
    tensor.dimensions[1] = VOCAB;
    tensor.dimension_count = 2;
    tensor.type = TEST_TYPE;
    tensor.data = (const uint8_t *)output_seeds;
    tensor.storage_bytes = sizeof output_seeds;
    uint32_t want = UINT32_MAX, want_second = UINT32_MAX;
    float best = -3.402823466e+38f, best_second = -3.402823466e+38f;
    for (uint32_t row = 0; row < VOCAB; row++) {
      CHECK(aiueos_qwen35_dequantize_row(TEST_TYPE,
                                         (const uint8_t *)&output_seeds[row],
                                         EMBED, reference_row));
      float logit = reference_dot(reference_row, output_input);
      if (logit > best) {
        best_second = best; want_second = want; best = logit; want = row;
      } else if (logit > best_second) {
        best_second = logit; want_second = row;
      }
    }
    uint32_t token = 0, second = 0;
    float logit = 0.0f, second_logit = 0.0f;
    CHECK(aiueos_qwen35_test_output_select(&tensor, VOCAB, output_input,
                                           output_logits, output_row,
                                           &token, &second,
                                           &logit, &second_logit));
    CHECK(token == want && second == want_second);
    CHECK(float_bits(logit) == float_bits(best));
    CHECK(float_bits(second_logit) == float_bits(best_second));
    CHECK(want == 2U * FFN + 1U && want_second == 4U);
    /* a vocab that disagrees with the tensor is refused, not read past */
    CHECK(!aiueos_qwen35_test_output_select(&tensor, VOCAB - 1U,
                                            output_input, output_logits,
                                            output_row, &token, &second,
                                            &logit, &second_logit));
  }

  puts("AIUEOS_QWEN35_DECODE_MATH_OK softplus=reference rope=partial64 recurrent=delta-rule qk=repeat-interleave score=double output=views3");
  return 0;
}
