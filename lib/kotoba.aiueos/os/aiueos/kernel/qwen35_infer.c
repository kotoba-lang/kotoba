/* SPDX-License-Identifier: Apache-2.0 */
#include "qwen35_infer.h"
#include "qwen35_quant.h"

#include <stdint.h>

#ifdef AIUEOS_QWEN35_SMP
#include "smp.h"
#endif

#define EMBED 5120U
#define FFN 17408U
#define LINEAR_QKV 10240U
#define LINEAR_INNER 6144U
#define FULL_QG 12288U
#define FULL_VALUE 1024U
#define HEAD_DIM 256U
#define LINEAR_HEAD_DIM 128U
#define LINEAR_KEY_HEADS 16U
#define LINEAR_VALUE_HEADS 48U
#define LINEAR_KV_GROUP_SIZE (LINEAR_VALUE_HEADS / LINEAR_KEY_HEADS)
#define EPSILON 0.000001f
#define LINEAR_CONV_HISTORY 3U
#define FULL_KV_WIDTH 1024U
#define FULL_GATE_TEMP_OFFSET FULL_VALUE
#define FULL_KEY_TEMP_OFFSET (FULL_GATE_TEMP_OFFSET + HEAD_DIM)
#define ROPE_DIM 64U
#define ROPE_HALF 32U
#define ROPE_LOG_THETA 16.11809565095832f
#define INV_SQRT_HEAD_DIM 0.0625f
#define INV_SQRT_LINEAR_HEAD_DIM 0.08838834764831845f

struct qwen35_workspace {
  float state[EMBED];
  float normalized[EMBED];
  float scratch_a[FFN];
  float scratch_b[FFN];
  float scratch_c[FULL_QG];
  float dequantized[FFN];
  float ap_dequantized[FFN];
  float beta_values[48];
};

typedef char qwen35_workspace_size[
    (sizeof(struct qwen35_workspace) == AIUEOS_QWEN35_WORKSPACE_BYTES) ? 1 : -1];

struct qwen35_decode_context {
  float *recurrent;
  float *conv;
  float *full_key;
  float *full_value;
  float *full_key_shadow;
  uint64_t *full_key_hash;
  uint32_t position;
};

static float *state;
static float *normalized;
static float *scratch_a;
static float *scratch_b;
static float *scratch_c;
static float *dequantized;
static float *ap_dequantized;
static float *beta_values;
static uint32_t qwen_vector_bits;
static uint32_t qwen_worker_threads = 1U;
static uint32_t qwen_force_scalar;
static uint32_t qwen_failure_stage;

const char *aiueos_qwen35_failure_stage_label(uint32_t stage) {
  switch (stage) {
    case AIUEOS_QWEN35_FAILURE_EMBEDDING: return "EMBEDDING";
    case AIUEOS_QWEN35_FAILURE_ATTENTION_PROJECTION: return "ATTN PROJ";
    case AIUEOS_QWEN35_FAILURE_LINEAR_ALPHA: return "ALPHA";
    case AIUEOS_QWEN35_FAILURE_LINEAR_CONV: return "CONV";
    case AIUEOS_QWEN35_FAILURE_LINEAR_DECAY: return "DECAY";
    case AIUEOS_QWEN35_FAILURE_LINEAR_RECURRENT: return "RECURRENT";
    case AIUEOS_QWEN35_FAILURE_LINEAR_OUTPUT: return "LINEAR OUT";
    case AIUEOS_QWEN35_FAILURE_FULL_KEY: return "FULL KEY";
    case AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX: return "SOFTMAX";
    case AIUEOS_QWEN35_FAILURE_FULL_OUTPUT: return "FULL OUT";
    case AIUEOS_QWEN35_FAILURE_FFN: return "FFN";
    case AIUEOS_QWEN35_FAILURE_STATE_NONFINITE: return "STATE NAN";
    case AIUEOS_QWEN35_FAILURE_OUTPUT_NORM: return "OUTPUT NORM";
    case AIUEOS_QWEN35_FAILURE_OUTPUT_LOGITS: return "LOGITS NAN";
    case AIUEOS_QWEN35_FAILURE_FULL_QUERY: return "FULL QUERY";
    case AIUEOS_QWEN35_FAILURE_FULL_CACHE: return "KV CACHE";
    default: return "UNKNOWN";
  }
}

static int finite_float(float value) {
  union { float value; uint32_t bits; } representation = {value};
  return (representation.bits & 0x7f800000U) != 0x7f800000U;
}

static int finite_values(const float *values, uint64_t count) {
  for (uint64_t index = 0; index < count; index++)
    if (!finite_float(values[index])) return 0;
  return 1;
}

static uint64_t float_values_hash(const float *values, uint64_t count) {
  uint64_t hash = 14695981039346656037ULL;
  for (uint64_t index = 0; index < count; index++) {
    union { float value; uint32_t bits; } representation = {values[index]};
    for (uint32_t byte = 0; byte < 4U; byte++) {
      hash ^= (representation.bits >> (byte * 8U)) & 0xffU;
      hash *= 1099511628211ULL;
    }
  }
  return hash;
}

static int stable_attention_score(const float *query, const float *key,
                                  uint32_t count, double *score) {
  if (!score || !finite_values(query, count) || !finite_values(key, count))
    return 0;
  double sum0 = 0.0, sum1 = 0.0, sum2 = 0.0, sum3 = 0.0;
  uint32_t index = 0;
  for (; index + 4U <= count; index += 4U) {
    sum0 += (double)query[index + 0U] * (double)key[index + 0U];
    sum1 += (double)query[index + 1U] * (double)key[index + 1U];
    sum2 += (double)query[index + 2U] * (double)key[index + 2U];
    sum3 += (double)query[index + 3U] * (double)key[index + 3U];
  }
  double sum = (sum0 + sum1) + (sum2 + sum3);
  for (; index < count; index++)
    sum += (double)query[index] * (double)key[index];
  *score = sum * (double)INV_SQRT_HEAD_DIM;
  return *score == *score && *score <= 1.7976931348623157e+308 &&
         *score >= -1.7976931348623157e+308;
}

static int fail_at(uint32_t stage) {
  if (qwen_failure_stage == AIUEOS_QWEN35_FAILURE_NONE)
    qwen_failure_stage = stage;
  return 0;
}

void aiueos_qwen35_force_scalar(void) {
  qwen_force_scalar = 1U;
  qwen_vector_bits = 0U;
}

static float local_sqrt(float value) {
#if defined(__x86_64__)
  float result;
  __asm__ volatile("sqrtss %1, %0" : "=x"(result) : "x"(value));
  return result;
#else
  return __builtin_sqrtf(value);
#endif
}

static float local_exp(float value) {
  if (value <= -87.0f) return 0.0f;
  if (value >= 88.0f) value = 88.0f;
  float scaled = value * 1.4426950408889634f;
  int32_t exponent = scaled >= 0.0f ? (int32_t)(scaled + 0.5f)
                                     : (int32_t)(scaled - 0.5f);
  float remainder = value - (float)exponent * 0.6931471805599453f;
  float square = remainder * remainder;
  float polynomial =
      1.0f + remainder + square *
      (0.5f + remainder *
      (0.1666666716f + remainder *
      (0.0416666679f + remainder *
      (0.0083333310f + remainder * 0.0013888949f))));
  union { uint32_t bits; float value; } power = {
      (uint32_t)(exponent + 127) << 23
  };
  return polynomial * power.value;
}

static float local_log1p(float value) {
  /* log(1+x) = 2 * atanh(x/(2+x)); for x in [0,1] the transformed
     argument is at most 1/3 and this odd series is float-accurate. */
  float z = value / (2.0f + value);
  float z2 = z * z;
  float term = z;
  float sum = term;
  term *= z2; sum += term * (1.0f / 3.0f);
  term *= z2; sum += term * (1.0f / 5.0f);
  term *= z2; sum += term * (1.0f / 7.0f);
  term *= z2; sum += term * (1.0f / 9.0f);
  term *= z2; sum += term * (1.0f / 11.0f);
  term *= z2; sum += term * (1.0f / 13.0f);
  return 2.0f * sum;
}

static float softplus(float value) {
  if (value >= 20.0f) return value;
  if (value <= -20.0f) return local_exp(value);
  if (value >= 0.0f) return value + local_log1p(local_exp(-value));
  return local_log1p(local_exp(value));
}

#if AIUEOS_QWEN35_KOTOBA_PARITY == 5 || defined(AIUEOS_QWEN35_C_REFERENCE_ROPE)
static void local_sincos(float value, float *sine, float *cosine) {
#if defined(__x86_64__)
  float s, c;
  __asm__ volatile("fsincos" : "=t"(c), "=u"(s) : "0"(value));
  *sine = s;
  *cosine = c;
#else
  *sine = __builtin_sinf(value);
  *cosine = __builtin_cosf(value);
#endif
}
#endif

static float sigmoid(float value) {
  if (value >= 0.0f) {
    float e = local_exp(-value);
    return 1.0f / (1.0f + e);
  }
  float e = local_exp(value);
  return e / (1.0f + e);
}

static float silu(float value) {
  return value * sigmoid(value);
}

static uint64_t read_cycles(void) {
#if defined(__x86_64__)
  uint32_t low, high;
  __asm__ volatile("lfence; rdtsc" : "=a"(low), "=d"(high) : : "memory");
  return ((uint64_t)high << 32) | low;
#else
  return 0;
#endif
}

static float dot_scalar(const float * left, const float * right,
                        uint64_t count) {
  float sum0 = 0.0f, sum1 = 0.0f, sum2 = 0.0f, sum3 = 0.0f;
  uint64_t index = 0;
  for (; index + 4 <= count; index += 4) {
    sum0 += left[index + 0] * right[index + 0];
    sum1 += left[index + 1] * right[index + 1];
    sum2 += left[index + 2] * right[index + 2];
    sum3 += left[index + 3] * right[index + 3];
  }
  float sum = (sum0 + sum1) + (sum2 + sum3);
  for (; index < count; index++) sum += left[index] * right[index];
  return sum;
}

#if defined(__x86_64__) && !defined(AIUEOS_QWEN35_SCALAR)
typedef float qwen_v8f __attribute__((vector_size(32), aligned(1)));
typedef float qwen_v4f __attribute__((vector_size(16), aligned(1)));

static void prepare_bsp_extended_state(void) {
  uint32_t eax, ebx, ecx, edx;
  __asm__ volatile("cpuid"
                   : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                   : "a"(1U), "c"(0U));
  if ((ecx & ((1U << 26) | (1U << 28))) !=
      ((1U << 26) | (1U << 28))) return;
  uintptr_t cr4;
  __asm__ volatile("mov %%cr4, %0" : "=r"(cr4));
  cr4 |= (1U << 9) | (1U << 10) | (1U << 18);
  __asm__ volatile("mov %0, %%cr4" : : "r"(cr4) : "memory");
  uint32_t xcr0_low, xcr0_high;
  __asm__ volatile("xgetbv"
                   : "=a"(xcr0_low), "=d"(xcr0_high) : "c"(0U));
  xcr0_low |= 0x6U;
  __asm__ volatile("xsetbv"
                   : : "a"(xcr0_low), "d"(xcr0_high), "c"(0U));
}

__attribute__((target("avx2")))
static float dot_avx2(const float *left, const float *right, uint64_t count) {
  qwen_v4f sums = {0.0f, 0.0f, 0.0f, 0.0f};
  uint64_t index = 0;
  for (; index + 8U <= count; index += 8U) {
    qwen_v8f left8 = *(const qwen_v8f *)(const void *)(left + index);
    qwen_v8f right8 = *(const qwen_v8f *)(const void *)(right + index);
    qwen_v8f product = left8 * right8;
    qwen_v4f lower = __builtin_shufflevector(product, product, 0, 1, 2, 3);
    qwen_v4f upper = __builtin_shufflevector(product, product, 4, 5, 6, 7);
    /* Each SIMD lane is one of the scalar implementation's accumulators,
       and lower is added before upper just like two consecutive four-element
       scalar iterations. The final reduction below is NOT dot_scalar's
       (s0+s1)+(s2+s3), nor is the under-eight tail: QWEN-PARITY dot-avx2
       measures the distance (up to 1 ULP, ADR-0222). */
    sums += lower;
    sums += upper;
  }
  union { qwen_v4f vector; float lane[4]; } reduced = {sums};
  /* Four volatile updates prevent the optimizer from replacing the contract's
     left-to-right final reduction with a different horizontal tree. */
  volatile float ordered = reduced.lane[0];
  ordered += reduced.lane[1];
  ordered += reduced.lane[2];
  ordered += reduced.lane[3];
  float sum = ordered;
  for (; index < count; index++) sum += left[index] * right[index];
  return sum;
}

static int cpu_has_avx2(void) {
  uint32_t eax, ebx, ecx, edx;
  __asm__ volatile("cpuid"
                   : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                   : "a"(0U), "c"(0U));
  if (eax < 7U) return 0;
  __asm__ volatile("cpuid"
                   : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                   : "a"(1U), "c"(0U));
  if ((ecx & ((1U << 27) | (1U << 28))) !=
      ((1U << 27) | (1U << 28))) return 0;
  uint32_t xcr0_low, xcr0_high;
  __asm__ volatile("xgetbv"
                   : "=a"(xcr0_low), "=d"(xcr0_high) : "c"(0U));
  if ((xcr0_low & 0x6U) != 0x6U) return 0;
  __asm__ volatile("cpuid"
                   : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                   : "a"(7U), "c"(0U));
  return (ebx & (1U << 5)) != 0;
}
#endif

static float dot(const float *left, const float *right, uint64_t count) {
#if defined(__x86_64__) && !defined(AIUEOS_QWEN35_SCALAR)
  if (qwen_vector_bits == 256U) return dot_avx2(left, right, count);
#endif
  return dot_scalar(left, right, count);
}

#ifndef AIUEOS_QWEN35_C_REFERENCE_MATVEC
extern uint64_t kotoba_aiueos_qwen35_dequant_row(uint64_t type,
                                                 const uint8_t *source,
                                                 uint64_t source_bytes,
                                                 float *destination,
                                                 uint64_t destination_bytes);
#endif
#if AIUEOS_QWEN35_KOTOBA_PARITY == 1 || !defined(AIUEOS_QWEN35_C_REFERENCE_MATVEC)
extern uint64_t kotoba_aiueos_qwen35_dot_f32(const float *left,
                                             uint64_t left_bytes,
                                             const float *right,
                                             uint64_t right_bytes,
                                             uint64_t count);
#endif

/* One row of a tensor as binary32. The dequantiser is the Kotoba object
   `aiueos-qwen35-dequant-row` (ADR-0221; all fifteen of the artifact's
   types); the C `aiueos_qwen35_dequantize_row` is the reference the parity
   self-test compares it against and what the host smokes run
   (`-DAIUEOS_QWEN35_C_REFERENCE_MATVEC`, a machine that cannot link a kernel
   object). What stays here is the row's address arithmetic and its bound. */
static int tensor_row(const struct aiueos_qwen35_tensor *tensor,
                      uint64_t row, float *output) {
  if (!tensor || !tensor->data || tensor->dimension_count != 2 ||
      row >= tensor->dimensions[1] || tensor->dimensions[0] > FFN) return 0;
  uint64_t row_bytes =
      aiueos_qwen35_quant_row_bytes(tensor->type, tensor->dimensions[0]);
  if (!row_bytes || row > UINT64_MAX / row_bytes ||
      row * row_bytes > tensor->storage_bytes ||
      row_bytes > tensor->storage_bytes - row * row_bytes) return 0;
#ifdef AIUEOS_QWEN35_C_REFERENCE_MATVEC
  return aiueos_qwen35_dequantize_row(
      tensor->type, tensor->data + row * row_bytes,
      tensor->dimensions[0], output);
#else
  return kotoba_aiueos_qwen35_dequant_row(
      tensor->type, tensor->data + row * row_bytes, row_bytes,
      output, tensor->dimensions[0] * 4U) == 0;
#endif
}

/* The C matvec, KEPT AS THE REFERENCE and no longer the live path (ADR-0221).
   The parity self-test (AIUEOS_QWEN35_KOTOBA_PARITY=1) compares the object
   against it on the CPU. `-DAIUEOS_QWEN35_C_REFERENCE_MATVEC` makes it the
   forward pass again, for two builds only: the host smokes (a machine that
   cannot link a kernel object) and parity profiles 2-4 (which link only
   their own stage's objects to fit the low region, build-uefi.sh). It leaves this file when the K16 has measured the
   object's token rate (ADR-0221's next step). */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 1 || defined(AIUEOS_QWEN35_C_REFERENCE_MATVEC)
static int matvec_range_c(const struct aiueos_qwen35_tensor *tensor,
                          const float *input, uint64_t input_count,
                          float *output, uint64_t first, uint64_t end,
                          float *row_values) {
  for (uint64_t row = first; row < end; row++) {
    if (!tensor_row(tensor, row, row_values)) return 0;
    output[row] = dot(row_values, input, input_count);
  }
  return 1;
}
#endif

#ifdef AIUEOS_QWEN35_C_REFERENCE_MATVEC
static int matvec_range(const struct aiueos_qwen35_tensor *tensor,
                        const float *input, uint64_t input_count,
                        float *output, uint64_t first, uint64_t end,
                        float *row_values) {
  return matvec_range_c(tensor, input, input_count, output, first, end,
                        row_values);
}
#else
/* THE LIVE MATVEC IS THE KOTOBA OBJECT (ADR-0221). `aiueos-qwen35-matvec`
   dequantises each row of a quantised tensor (all fifteen of the artifact's
   types, ADR-0221) and takes its four-accumulator dot product with the input,
   exactly as `matvec_range_c` above did, and the parity self-test holds the
   two to the same bits. What stays here is MARSHALLING: the object takes
   ONE arena and a 96-byte plan of offsets into it (five arguments cannot
   carry four regions), so the arena is the identity-mapped address space
   from page 1 to the 64 GiB model identity limit and every offset is an
   address minus 4096 -- the object never touches a byte outside the four
   regions the plan names, and its own bounds proof is the region check.

   The object also caps the work of one call at 2,097,152 multiply-adds
   (a fuel bound that does not move with the tensor, see its header), so a
   tensor is handed over in row chunks of `2097152 / cols` -- 409 rows of
   an EMBED-wide tensor, 120 of an FFN-wide one -- and a refusal partway
   leaves the output half written, which the return value says. */
extern uint64_t kotoba_aiueos_qwen35_matvec(uint8_t *arena, uint64_t arena_bytes,
                                            const uint8_t *plan,
                                            uint64_t plan_bytes);

#define QWEN_MATVEC_ARENA_BASE 4096ULL
#define QWEN_MATVEC_ARENA_END (64ULL * 1024ULL * 1024ULL * 1024ULL)
#define QWEN_MATVEC_WORK_CEILING 2097152ULL

static void qwen_plan_u32(uint8_t *plan, uint32_t at, uint32_t v) {
  plan[at] = (uint8_t)v; plan[at + 1] = (uint8_t)(v >> 8);
  plan[at + 2] = (uint8_t)(v >> 16); plan[at + 3] = (uint8_t)(v >> 24);
}

static void qwen_plan_u64(uint8_t *plan, uint32_t at, uint64_t v) {
  qwen_plan_u32(plan, at, (uint32_t)v);
  qwen_plan_u32(plan, at + 4, (uint32_t)(v >> 32));
}

static int matvec_range(const struct aiueos_qwen35_tensor *tensor,
                        const float *input, uint64_t input_count,
                        float *output, uint64_t first, uint64_t end,
                        float *row_values) {
  /* one plan per caller: the BSP and the AP run this concurrently under
     AIUEOS_QWEN35_SMP, each with its own scratch, so the plan lives on the
     stack (96 bytes) rather than in .bss */
  uint8_t plan[96];
  uint64_t rows, cols, row_bytes, chunk, row;
  if (!tensor || !tensor->data || tensor->dimension_count != 2 ||
      tensor->dimensions[0] != input_count || first > end ||
      end > tensor->dimensions[1]) return 0;
  rows = tensor->dimensions[1];
  cols = tensor->dimensions[0];
  row_bytes = aiueos_qwen35_quant_row_bytes(tensor->type, cols);
  if (!row_bytes || rows * row_bytes > tensor->storage_bytes) return 0;
  if ((uint64_t)(uintptr_t)tensor->data < QWEN_MATVEC_ARENA_BASE ||
      (uint64_t)(uintptr_t)input < QWEN_MATVEC_ARENA_BASE ||
      (uint64_t)(uintptr_t)output < QWEN_MATVEC_ARENA_BASE ||
      (uint64_t)(uintptr_t)row_values < QWEN_MATVEC_ARENA_BASE) return 0;
  for (row = 0; row < 96; row++) plan[row] = 0;
  qwen_plan_u32(plan, 0, tensor->type);
  qwen_plan_u64(plan, 8, rows);
  qwen_plan_u64(plan, 16, cols);
  qwen_plan_u64(plan, 24, (uint64_t)(uintptr_t)tensor->data - QWEN_MATVEC_ARENA_BASE);
  qwen_plan_u64(plan, 32, rows * row_bytes);
  qwen_plan_u64(plan, 40, (uint64_t)(uintptr_t)input - QWEN_MATVEC_ARENA_BASE);
  qwen_plan_u64(plan, 48, (uint64_t)(uintptr_t)output - QWEN_MATVEC_ARENA_BASE);
  qwen_plan_u64(plan, 56, (uint64_t)(uintptr_t)row_values - QWEN_MATVEC_ARENA_BASE);
  chunk = QWEN_MATVEC_WORK_CEILING / cols;
  if (!chunk) return 0;
  for (row = first; row < end; row += chunk) {
    uint64_t stop = end - row < chunk ? end : row + chunk;
    qwen_plan_u64(plan, 64, row);
    qwen_plan_u64(plan, 72, stop);
    if (kotoba_aiueos_qwen35_matvec((uint8_t *)(uintptr_t)QWEN_MATVEC_ARENA_BASE,
                                    QWEN_MATVEC_ARENA_END - QWEN_MATVEC_ARENA_BASE,
                                    plan, 96) != 0)
      return 0;
  }
  return 1;
}
#endif

#ifdef AIUEOS_QWEN35_SMP
struct matvec_ap_task {
  const struct aiueos_qwen35_tensor *tensor;
  const float *input;
  uint64_t input_count;
  float *output;
  uint64_t first;
  uint64_t end;
  int ok;
};

static void matvec_ap(void *opaque) {
  struct matvec_ap_task *task = opaque;
  task->ok = matvec_range(task->tensor, task->input, task->input_count,
                          task->output, task->first, task->end,
                          ap_dequantized);
}
#endif

static int matvec(const struct aiueos_qwen35_tensor *tensor,
                  const float *input, uint64_t input_count,
                  float *output, uint64_t output_count) {
  if (!tensor || tensor->dimension_count != 2 ||
      tensor->dimensions[0] != input_count ||
      tensor->dimensions[1] != output_count) return 0;
#ifdef AIUEOS_QWEN35_SMP
  if (qwen_worker_threads == 2U && output_count >= 512U) {
    uint64_t split = output_count / 2U;
    struct matvec_ap_task task = {
      .tensor = tensor, .input = input, .input_count = input_count,
      .output = output, .first = split, .end = output_count, .ok = 0
    };
    if (aiueos_smp_dispatch(matvec_ap, &task)) {
      int bsp_ok = matvec_range(tensor, input, input_count, output, 0, split,
                                dequantized);
      int ap_ok = aiueos_smp_join() && task.ok;
      return bsp_ok && ap_ok;
    }
  }
#endif
  return matvec_range(tensor, input, input_count, output, 0, output_count,
                      dequantized);
}

static const float *f32_vector(const struct aiueos_qwen35_tensor *tensor,
                               uint64_t count) {
  if (!tensor || !tensor->data || tensor->type != AIUEOS_GGML_F32 ||
      tensor->dimension_count != 1 || tensor->dimensions[0] != count ||
      tensor->storage_bytes != count * sizeof(float)) return 0;
  return (const float *)(const void *)tensor->data;
}

/* The three normalisations and the elementwise activations, KEPT AS THE
   REFERENCE and no longer the live path (ADR-0220 cutover stage 2): parity
   profile 2 (AIUEOS_QWEN35_KOTOBA_PARITY=2) compares `aiueos-qwen35-norm` and
   `aiueos-qwen35-activation` against them on the CPU, and
   `-DAIUEOS_QWEN35_C_REFERENCE_NORM` makes them the forward pass again for
   the builds that cannot link those two objects: the host smokes and parity
   profiles 1, 3 and 4 (which link only their own stage's objects to fit the
   low region, build-uefi.sh). */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 2 || defined(AIUEOS_QWEN35_C_REFERENCE_NORM)
static int rms_norm_c(const float *input,
                      const struct aiueos_qwen35_tensor *weights,
                      uint64_t count, float *output) {
  if (!weights || !weights->data || weights->type != AIUEOS_GGML_F32 ||
      weights->dimension_count != 1 || weights->dimensions[0] != count ||
      weights->storage_bytes != count * sizeof(float)) return 0;
  double sum = 0.0;
  for (uint64_t index = 0; index < count; index++)
    sum += (double)(input[index] * input[index]);
  float mean = (float)(sum / (double)count);
  float scale = 1.0f / local_sqrt(mean + EPSILON);
  const float *weight = (const float *)(const void *)weights->data;
  for (uint64_t index = 0; index < count; index++)
    output[index] = input[index] * scale * weight[index];
  return 1;
}

static int rms_norm_heads_weighted_c(float *values, uint32_t heads,
                                     uint32_t width,
                                     const struct aiueos_qwen35_tensor *tensor) {
  const float *weights = f32_vector(tensor, width);
  if (!weights) return 0;
  for (uint32_t head = 0; head < heads; head++) {
    float *vector = values + head * width;
    double sum = 0.0;
    int ordinary = 1;
    float maximum = 0.0f;
    for (uint32_t index = 0; index < width; index++) {
      if (!finite_float(vector[index])) return 0;
      float magnitude = vector[index] < 0.0f ? -vector[index] : vector[index];
      if (magnitude > maximum) maximum = magnitude;
      float square = vector[index] * vector[index];
      if (!finite_float(square)) ordinary = 0;
      else sum += (double)square;
    }
    float scale;
    if (ordinary) {
      scale = 1.0f /
        local_sqrt((float)(sum / (double)width) + EPSILON);
    } else {
      double scaled_sum = 0.0;
      for (uint32_t index = 0; index < width; index++) {
        double scaled = (double)vector[index] / (double)maximum;
        scaled_sum += scaled * scaled;
      }
      double epsilon_scaled =
        (double)EPSILON / ((double)maximum * (double)maximum);
      scale = (1.0f / maximum) /
        local_sqrt((float)(scaled_sum / (double)width + epsilon_scaled));
    }
    if (!finite_float(scale)) return 0;
    for (uint32_t index = 0; index < width; index++) {
      vector[index] = vector[index] * scale * weights[index];
      if (!finite_float(vector[index])) return 0;
    }
  }
  return 1;
}

static void l2_norm_heads_c(float *values, uint32_t heads, uint32_t width) {
  for (uint32_t head = 0; head < heads; head++) {
    float *vector = values + head * width;
    double sum = 0.0;
    for (uint32_t index = 0; index < width; index++)
      sum += (double)(vector[index] * vector[index]);
    float scale = 1.0f / local_sqrt((float)sum + EPSILON);
    for (uint32_t index = 0; index < width; index++) vector[index] *= scale;
  }
}

/* `linear_attention`'s kernel-4 depthwise conv, KEPT AS THE REFERENCE
   (aiueos ADR-0222): activation modes 5 and 6 are the live path, and parity
   profile 2 compares them against this.  `history` is the channel-major
   three-entry cache or null; `position` nonzero reads it (mode 6), and a
   history is shifted either way. */
static void conv4_c(float *values, const float *kernel, float *history_base,
                    uint64_t position, uint64_t count) {
  for (uint64_t channel = 0; channel < count; channel++) {
    float current = values[channel];
    float mixed = current * kernel[channel * 4U + 3U];
    if (history_base) {
      float *history = history_base + channel * LINEAR_CONV_HISTORY;
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

/* `linear_attention`'s output norm and gate, KEPT AS THE REFERENCE (aiueos
   ADR-0222): norm mode 3 followed by activation mode 4 is the live path, and
   parity profile 2 compares them against this.  The gate arrives raw and is
   silu'd here; the per-head RMS has no finiteness refusals and no rescaled
   fallback, which is why it is not `rms_norm_heads_weighted`. */
static void linear_output_norm_c(float *values, float *gate, uint32_t heads,
                                 uint32_t width, const float *weights) {
  for (uint32_t index = 0; index < heads * width; index++)
    gate[index] = silu(gate[index]);
  for (uint32_t head = 0; head < heads; head++) {
    float *vector = values + head * width;
    double sum = 0.0;
    for (uint32_t index = 0; index < width; index++)
      sum += (double)(vector[index] * vector[index]);
    float scale = 1.0f /
        local_sqrt((float)(sum / (double)width) + EPSILON);
    for (uint32_t index = 0; index < width; index++) {
      uint32_t position = head * width + index;
      vector[index] = vector[index] * scale * weights[index] *
                      gate[position];
    }
  }
}

#endif

/* The activation modes of `aiueos-qwen35-activation`, in its own numbering. */
#define QWEN_ACT_SILU 0U
#define QWEN_ACT_SIGMOID 1U
#define QWEN_ACT_SOFTPLUS 2U
#define QWEN_ACT_EXP 3U
#define QWEN_ACT_SILU_GATE 4U
#define QWEN_ACT_CONV4_FIRST 5U
#define QWEN_ACT_CONV4_NEXT 6U

#if AIUEOS_QWEN35_KOTOBA_PARITY == 2 || !defined(AIUEOS_QWEN35_C_REFERENCE_NORM)
extern uint64_t kotoba_aiueos_qwen35_activation(uint64_t mode, float *a,
                                                const float *b, uint64_t count,
                                                uint64_t spare);
/* Every argument as a word: mode 0 reads `b` as a POINTER (the weights) while
   modes 1 and 2 read it as a head COUNT, so a typed declaration would have to
   lie about one of them. */
extern uint64_t kotoba_aiueos_qwen35_norm(uint64_t mode, uint64_t a, uint64_t b,
                                          uint64_t c, uint64_t d);
#endif

#ifdef AIUEOS_QWEN35_C_REFERENCE_NORM
static int rms_norm(const float *input,
                    const struct aiueos_qwen35_tensor *weights,
                    uint64_t count, float *output) {
  return rms_norm_c(input, weights, count, output);
}

static int rms_norm_heads_weighted(float *values, uint32_t heads,
                                   uint32_t width,
                                   const struct aiueos_qwen35_tensor *tensor) {
  return rms_norm_heads_weighted_c(values, heads, width, tensor);
}

static int l2_norm_heads(float *values, uint32_t heads, uint32_t width) {
  l2_norm_heads_c(values, heads, width);
  return 1;
}

static int activate(uint32_t mode, float *values, const float *gate,
                    uint64_t count) {
  for (uint64_t index = 0; index < count; index++) {
    float x = values[index];
    values[index] =
      mode == QWEN_ACT_SILU ? silu(x) :
      mode == QWEN_ACT_SIGMOID ? sigmoid(x) :
      mode == QWEN_ACT_SOFTPLUS ? softplus(x) :
      mode == QWEN_ACT_EXP ? local_exp(x) :
                             silu(x) * gate[index];
  }
  return 1;
}

static int conv4(float *values, const float *kernel, float *history,
                 uint64_t position, uint64_t count) {
  conv4_c(values, kernel, history, position, count);
  return 1;
}

static float *linear_output_norm(float *values, float *gate, uint32_t heads,
                                 uint32_t width, const float *weights) {
  linear_output_norm_c(values, gate, heads, width, weights);
  return values;
}
#else
/* THE LIVE NORMS AND ACTIVATIONS ARE THE KOTOBA OBJECTS (ADR-0220 cutover
   stage 2). Both take raw addresses and write in place or into the output
   the caller names; zero is success and every other value is a refusal the
   caller turns into this file's failure stage, never ignores. What stays
   here is the tensor's shape check -- the object is handed a weight
   pointer, not a GGUF tensor. */
static int rms_norm(const float *input,
                    const struct aiueos_qwen35_tensor *weights,
                    uint64_t count, float *output) {
  const float *weight = f32_vector(weights, count);
  if (!weight) return 0;
  return kotoba_aiueos_qwen35_norm(0, (uint64_t)(uintptr_t)input,
                                   (uint64_t)(uintptr_t)weight, count,
                                   (uint64_t)(uintptr_t)output) == 0;
}

static int rms_norm_heads_weighted(float *values, uint32_t heads,
                                   uint32_t width,
                                   const struct aiueos_qwen35_tensor *tensor) {
  const float *weights = f32_vector(tensor, width);
  if (!weights) return 0;
  return kotoba_aiueos_qwen35_norm(2, (uint64_t)(uintptr_t)values, heads,
                                   width,
                                   (uint64_t)(uintptr_t)weights) == 0;
}

static int l2_norm_heads(float *values, uint32_t heads, uint32_t width) {
  return kotoba_aiueos_qwen35_norm(1, (uint64_t)(uintptr_t)values, heads,
                                   width, 0) == 0;
}

static int activate(uint32_t mode, float *values, const float *gate,
                    uint64_t count) {
  return kotoba_aiueos_qwen35_activation(mode, values, gate, count, 0) == 0;
}

/* The conv is modes 5 and 6 of the activation object, with the history's
   address in its fifth word. Mode 6 refuses a null history; a later token
   without a cache is not a state this pass can reach. */
static int conv4(float *values, const float *kernel, float *history,
                 uint64_t position, uint64_t count) {
  return kotoba_aiueos_qwen35_activation(
    position ? QWEN_ACT_CONV4_NEXT : QWEN_ACT_CONV4_FIRST, values, kernel,
    count, (uint64_t)(uintptr_t)history) == 0;
}

/* The output norm is mode 3 of the norm object, in place over `values`; the
   gate is then mode 4 of the activation object, `gate[i] = silu(gate[i]) *
   values[i]`, which is the C's `values[i] * silu(gate[i])` because binary32
   multiplication commutes.  The answer therefore lands in `gate`, and the
   pointer returned is where the caller reads it (the reference returns
   `values`).  Null is a refusal. */
static float *linear_output_norm(float *values, float *gate, uint32_t heads,
                                 uint32_t width, const float *weights) {
  if (kotoba_aiueos_qwen35_norm(3, (uint64_t)(uintptr_t)values, heads, width,
                                (uint64_t)(uintptr_t)weights) != 0 ||
      kotoba_aiueos_qwen35_activation(QWEN_ACT_SILU_GATE, gate, values,
                                      (uint64_t)heads * width, 0) != 0)
    return 0;
  return gate;
}
#endif

/* The C rotary embedding, KEPT AS A REFERENCE and no longer the live path
 * (ADR-0220 cutover stage 5, ADR-0222 item 6).  Unlike the stages before it,
 * the object is NOT bit-equal to this and is not meant to be: the sine here
 * is x87 `fsincos` and the frequency `local_exp`, while the object follows
 * Prism llama.cpp's iterated theta_scale and the language's bounded sine.
 * Parity profile 5 (AIUEOS_QWEN35_KOTOBA_PARITY=5) checks the object bit for
 * bit against the Prism reference and PRINTS how far this C is from it;
 * `-DAIUEOS_QWEN35_C_REFERENCE_ROPE` makes it the forward pass again for the
 * builds that do not link the object: the host smokes and parity profiles
 * 1-4. */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 5 || defined(AIUEOS_QWEN35_C_REFERENCE_ROPE)
static void rope_heads_c(float *values, uint32_t heads, uint32_t position) {
  if (!position) return;
  for (uint32_t pair = 0; pair < ROPE_HALF; pair++) {
    float frequency = local_exp(
      -ROPE_LOG_THETA * (float)pair / (float)ROPE_HALF);
    float sine, cosine;
    local_sincos((float)position * frequency, &sine, &cosine);
    for (uint32_t head = 0; head < heads; head++) {
      float *vector = values + head * HEAD_DIM;
      float first = vector[pair];
      float second = vector[pair + ROPE_HALF];
      vector[pair] = first * cosine - second * sine;
      vector[pair + ROPE_HALF] = second * cosine + first * sine;
    }
  }
}
#endif

#if AIUEOS_QWEN35_KOTOBA_PARITY == 5 || !defined(AIUEOS_QWEN35_C_REFERENCE_ROPE)
extern uint64_t kotoba_aiueos_qwen35_rope(float *values, uint64_t values_bytes,
                                          uint64_t heads, uint64_t position);
#endif

#ifdef AIUEOS_QWEN35_C_REFERENCE_ROPE
static int rope_heads(float *values, uint32_t heads, uint32_t position) {
  rope_heads_c(values, heads, position);
  return 1;
}
#else
/* THE LIVE ROTARY EMBEDDING IS THE KOTOBA OBJECT (ADR-0220 cutover stage 5).
 * In place over `heads` consecutive 256-float heads; zero is success.  Its
 * refusals are a null pointer, heads outside 1..64, a byte count that is not
 * heads * 1024 and a position past 25,735 -- the first three cannot happen
 * from the two call sites (24 and 4 heads of the workspace), the last cannot
 * happen while decode stops at AIUEOS_QWEN35_GENERATION_TOKENS, so any
 * non-zero answer is FULL KEY, the stage the rotation belongs to.  Position
 * zero is computed, not skipped (the identity for finite values). */
static int rope_heads(float *values, uint32_t heads, uint32_t position) {
  return kotoba_aiueos_qwen35_rope(values, (uint64_t)heads * HEAD_DIM * 4U,
                                   heads, position) == 0;
}
#endif

/* The gated DeltaNet step of one linear-attention head, KEPT AS THE
 * REFERENCE and no longer the live path (ADR-0220 cutover stage 4): parity
 * profile 4 (AIUEOS_QWEN35_KOTOBA_PARITY=4) compares
 * `aiueos-qwen35-recurrent-step` against it on the CPU, and
 * `-DAIUEOS_QWEN35_C_REFERENCE_RECURRENT` makes it the forward pass again for
 * the builds that do not link that object: the host smokes and parity
 * profiles 1, 2 and 3. */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 4 || defined(AIUEOS_QWEN35_C_REFERENCE_RECURRENT)
static void recurrent_step_c(float *head_state,
                             const float *key,
                             const float *query,
                             const float *value,
                             float decay,
                             float beta,
                             float *correction,
                             float *output) {
  for (uint32_t value_index = 0; value_index < LINEAR_HEAD_DIM;
       value_index++) {
    float remembered = 0.0f;
    for (uint32_t key_index = 0; key_index < LINEAR_HEAD_DIM; key_index++) {
      float *cell = head_state +
        (uint64_t)key_index * LINEAR_HEAD_DIM + value_index;
      *cell *= decay;
      remembered += *cell * key[key_index];
    }
    correction[value_index] = (value[value_index] - remembered) * beta;
  }
  for (uint32_t key_index = 0; key_index < LINEAR_HEAD_DIM; key_index++) {
    float k = key[key_index];
    float *row = head_state + (uint64_t)key_index * LINEAR_HEAD_DIM;
    for (uint32_t value_index = 0; value_index < LINEAR_HEAD_DIM;
         value_index++)
      row[value_index] += k * correction[value_index];
  }
  for (uint32_t value_index = 0; value_index < LINEAR_HEAD_DIM;
       value_index++) {
    float value_out = 0.0f;
    for (uint32_t key_index = 0; key_index < LINEAR_HEAD_DIM; key_index++)
      value_out += head_state[
        (uint64_t)key_index * LINEAR_HEAD_DIM + value_index] *
        query[key_index];
    output[value_index] = value_out * INV_SQRT_LINEAR_HEAD_DIM;
  }
}
#endif

#if AIUEOS_QWEN35_KOTOBA_PARITY == 4 || !defined(AIUEOS_QWEN35_C_REFERENCE_RECURRENT)
extern uint64_t kotoba_aiueos_qwen35_recurrent_step(uint8_t *arena,
                                                    uint64_t arena_bytes,
                                                    const uint8_t *plan,
                                                    uint64_t plan_bytes);
#endif

#ifdef AIUEOS_QWEN35_C_REFERENCE_RECURRENT
static int recurrent_step(float *head_state, const float *key,
                          const float *query, const float *value,
                          float decay, float beta, float *correction,
                          float *output) {
  recurrent_step_c(head_state, key, query, value, decay, beta, correction,
                   output);
  return 1;
}
#else
/* THE LIVE RECURRENT STEP IS THE KOTOBA OBJECT (ADR-0220 cutover stage 4).
 * Like the attention object, it takes ONE arena and a 96-byte plan of
 * offsets.  The live regions are not one allocation -- the head state lives
 * in `decode->recurrent`, the key/query/value, the correction row and the
 * output in the workspace -- so the arena is the smallest span that covers
 * all six and each offset is that region's distance from the span's base.
 * The extents are the object's own `regions-fit` extents (`d*d*4` for the
 * state, `d*4` for each vector), so the object cannot be asked to read past
 * the region it was handed.
 *
 * The plan is words: slot k is byte 8k.  Word 0 is the reserved mode word
 * (zero).  Word 1 is the dimension, words 2..7 the six regions, words 8 and
 * 9 the binary32 bit patterns of decay and beta, words 10 and 11 reserved
 * zero.  The decay and beta finiteness refusal (-6) is the object's; the
 * caller checks the same thing first and reports LINEAR_DECAY, so a -6 here
 * is unreachable and any non-zero answer is LINEAR_RECURRENT. */
static int recurrent_step(float *head_state, const float *key,
                          const float *query, const float *value,
                          float decay, float beta, float *correction,
                          float *output) {
  union { float value; uint32_t bits; } decay_bits = {decay}, beta_bits = {beta};
  uint64_t plan[12] = {0}, extent[12] = {0};
  uint64_t low = ~0ULL, high = 0;
  plan[1] = LINEAR_HEAD_DIM;
  plan[2] = (uint64_t)(uintptr_t)head_state;
  extent[2] = (uint64_t)LINEAR_HEAD_DIM * LINEAR_HEAD_DIM * 4U;
  plan[3] = (uint64_t)(uintptr_t)key;        extent[3] = LINEAR_HEAD_DIM * 4U;
  plan[4] = (uint64_t)(uintptr_t)query;      extent[4] = LINEAR_HEAD_DIM * 4U;
  plan[5] = (uint64_t)(uintptr_t)value;      extent[5] = LINEAR_HEAD_DIM * 4U;
  plan[6] = (uint64_t)(uintptr_t)correction; extent[6] = LINEAR_HEAD_DIM * 4U;
  plan[7] = (uint64_t)(uintptr_t)output;     extent[7] = LINEAR_HEAD_DIM * 4U;
  plan[8] = decay_bits.bits;
  plan[9] = beta_bits.bits;
  for (uint32_t slot = 0; slot < 12U; slot++) {
    if (!extent[slot]) continue;
    if (plan[slot] < low) low = plan[slot];
    if (plan[slot] + extent[slot] > high) high = plan[slot] + extent[slot];
  }
  for (uint32_t slot = 0; slot < 12U; slot++)
    if (extent[slot]) plan[slot] -= low;
  return kotoba_aiueos_qwen35_recurrent_step(
             (uint8_t *)(uintptr_t)low, high - low,
             (const uint8_t *)(const void *)plan, 96) == 0;
}
#endif

/* The position-zero / cache-free coefficient of `linear_attention`,
 * beta * dot(q, k) / sqrt(d).  The dot is the Kotoba object
 * `aiueos-qwen35-dot-f32` (dot_scalar's tree, already linked in the model
 * image); the two products stay C, like the decay transition's.  The C dot
 * it replaces was `dot`, i.e. dot_avx2 on an AVX2 CPU, which is up to 1 ULP
 * away from this tree (QWEN-PARITY dot-avx2, ADR-0222) -- the same move the
 * output projection made.  `linear_zero_coefficient_c` is the reference:
 * the host smokes and parity profiles 2-5 (`-DAIUEOS_QWEN35_C_REFERENCE_
 * MATVEC`, no dot object linked) run it as the forward pass, and parity
 * profile 1 compares the live wrapper against it. */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 1 || defined(AIUEOS_QWEN35_C_REFERENCE_MATVEC)
static float linear_zero_coefficient_c(const float *query, const float *key,
                                       float beta) {
  return dot_scalar(query, key, LINEAR_HEAD_DIM) * INV_SQRT_LINEAR_HEAD_DIM *
         beta;
}
#endif

static int linear_zero_coefficient(const float *query, const float *key,
                                   float beta, float *coefficient) {
#ifdef AIUEOS_QWEN35_C_REFERENCE_MATVEC
  *coefficient = linear_zero_coefficient_c(query, key, beta);
  return 1;
#else
  uint64_t answer = kotoba_aiueos_qwen35_dot_f32(
      query, LINEAR_HEAD_DIM * 4U, key, LINEAR_HEAD_DIM * 4U, LINEAR_HEAD_DIM);
  /* A sum is its binary32 bits sign-extended; a refusal is below INT32_MIN. */
  union { uint32_t bits; float value; } sum = {(uint32_t)answer};
  if (answer != (uint64_t)(int64_t)(int32_t)sum.bits) return 0;
  *coefficient = sum.value * INV_SQRT_LINEAR_HEAD_DIM * beta;
  return 1;
#endif
}

static int ffn(const struct aiueos_qwen35_layer *layer) {
  if (!rms_norm(state, &layer->post_attention_norm, EMBED, normalized) ||
      !matvec(&layer->ffn_gate, normalized, EMBED, scratch_a, FFN) ||
      !matvec(&layer->ffn_up, normalized, EMBED, scratch_b, FFN) ||
      !activate(QWEN_ACT_SILU_GATE, scratch_a, scratch_b, FFN))
    return 0;
  if (!matvec(&layer->ffn_down, scratch_a, FFN, scratch_b, EMBED)) return 0;
  for (uint32_t index = 0; index < EMBED; index++) state[index] += scratch_b[index];
  return 1;
}

static const float *resolved_cached_key(
    struct qwen35_decode_context *decode, uint64_t cache_entry,
    uint32_t kv_head) {
  if (!decode || kv_head >= 4U) return 0;
  float *primary = decode->full_key + cache_entry * FULL_KV_WIDTH;
  uint64_t expected_hash = decode->full_key_hash[cache_entry];
  if (!expected_hash || !finite_values(primary, FULL_KV_WIDTH) ||
      float_values_hash(primary, FULL_KV_WIDTH) != expected_hash) {
    const float *shadow =
      decode->full_key_shadow + cache_entry * FULL_KV_WIDTH;
    if (!finite_values(shadow, FULL_KV_WIDTH) ||
        float_values_hash(shadow, FULL_KV_WIDTH) != expected_hash)
      return 0;
    for (uint32_t index = 0; index < FULL_KV_WIDTH; index++)
      primary[index] = shadow[index];
  }
  return primary + kv_head * HEAD_DIM;
}

static int linear_attention(const struct aiueos_qwen35_layer *layer,
                            struct qwen35_decode_context *decode,
                            uint32_t linear_slot) {
  const struct aiueos_qwen35_linear_tensors *linear = &layer->mixer.linear;
  if (!rms_norm(state, &layer->attention_norm, EMBED, normalized) ||
      !matvec(&linear->qkv, normalized, EMBED, scratch_a, LINEAR_QKV) ||
      !matvec(&linear->gate, normalized, EMBED, scratch_b, LINEAR_INNER) ||
      !matvec(&linear->beta, normalized, EMBED, beta_values, 48))
    return fail_at(AIUEOS_QWEN35_FAILURE_ATTENTION_PROJECTION);

  if (decode && decode->position &&
      !matvec(&linear->alpha, normalized, EMBED, ap_dequantized, 48))
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_ALPHA);

  if (!linear->conv1d.data || linear->conv1d.type != AIUEOS_GGML_F32 ||
      linear->conv1d.dimension_count != 2 ||
      linear->conv1d.dimensions[0] != 4 ||
      linear->conv1d.dimensions[1] != LINEAR_QKV)
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_CONV);
  const float *kernel = (const float *)(const void *)linear->conv1d.data;
  float *conv = decode ? decode->conv +
    (uint64_t)linear_slot * LINEAR_QKV * LINEAR_CONV_HISTORY : 0;
  if (!conv4(scratch_a, kernel, conv, conv ? decode->position : 0,
             LINEAR_QKV) ||
      !activate(QWEN_ACT_SILU, scratch_a, 0, LINEAR_QKV))
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_CONV);

  if (!l2_norm_heads(scratch_a, 16, LINEAR_HEAD_DIM) ||
      !l2_norm_heads(scratch_a + 2048, 16, LINEAR_HEAD_DIM))
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_CONV);
  /* beta_values holds sigmoid(beta) from here on: both branches below read
     it only through the sigmoid, which is now one call over the 48 heads. */
  if (!activate(QWEN_ACT_SIGMOID, beta_values, 0, 48))
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_DECAY);

  if (!decode) {
    for (uint32_t head = 0; head < 48; head++) {
      uint32_t key_head = head / LINEAR_KV_GROUP_SIZE;
      float coefficient;
      if (!linear_zero_coefficient(
              scratch_a + key_head * LINEAR_HEAD_DIM,
              scratch_a + 2048U + key_head * LINEAR_HEAD_DIM,
              beta_values[head], &coefficient))
        return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_RECURRENT);
      for (uint32_t index = 0; index < LINEAR_HEAD_DIM; index++)
        scratch_c[head * LINEAR_HEAD_DIM + index] =
            scratch_a[4096U + head * LINEAR_HEAD_DIM + index] * coefficient;
    }
  } else {
    const float *a = f32_vector(&linear->a, 48);
    const float *dt = f32_vector(&linear->dt_bias, 48);
    if (!a || !dt) return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_DECAY);
    float *layer_state = decode->recurrent +
      (uint64_t)linear_slot * 48U * LINEAR_HEAD_DIM * LINEAR_HEAD_DIM;
    /* decay = exp(a * softplus(alpha + dt_bias)), per head, as two object
       calls over the 48 heads with the product between them. ap_dequantized
       holds the alpha projection (written above, read nowhere else) and is
       turned into the decay in place. Every transition is checked finite
       before any exponential is taken, as the per-head C did. */
    if (decode->position) {
      for (uint32_t head = 0; head < 48; head++)
        ap_dequantized[head] = ap_dequantized[head] + dt[head];
      if (!activate(QWEN_ACT_SOFTPLUS, ap_dequantized, 0, 48))
        return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_DECAY);
      for (uint32_t head = 0; head < 48; head++) {
        ap_dequantized[head] = a[head] * ap_dequantized[head];
        if (!finite_float(ap_dequantized[head]))
          return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_DECAY);
      }
      if (!activate(QWEN_ACT_EXP, ap_dequantized, 0, 48))
        return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_DECAY);
    }
    for (uint32_t head = 0; head < 48; head++) {
      uint32_t key_head = head / LINEAR_KV_GROUP_SIZE;
      const float *query = scratch_a + key_head * LINEAR_HEAD_DIM;
      const float *key = scratch_a + 2048U + key_head * LINEAR_HEAD_DIM;
      const float *value = scratch_a + 4096U + head * LINEAR_HEAD_DIM;
      float *head_state = layer_state +
        (uint64_t)head * LINEAR_HEAD_DIM * LINEAR_HEAD_DIM;
      float decay = decode->position ? ap_dequantized[head] : 1.0f;
      float beta = beta_values[head];
      if (!finite_float(decay) || !finite_float(beta))
        return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_DECAY);

      float *output = scratch_c + head * LINEAR_HEAD_DIM;
      /* S <- decay*S; delta <- beta*(v-k^T S); S <- S+k*delta;
         y <- (q/sqrt(d))^T S.  Rows are key dimension, columns value. */
      if (!recurrent_step(head_state, key, query, value, decay, beta,
                          dequantized, output) ||
          !finite_values(output, LINEAR_HEAD_DIM))
        return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_RECURRENT);
      if (!decode->position) {
        /* With an all-zero recurrent state the official delta rule reduces
           exactly to v * beta * dot(q, k) / sqrt(d).  Keep the state written
           by recurrent_step, but preserve the already physically-qualified
           position-zero reduction order for the emitted activation.  The two
           forms are algebraically identical; fixing the association here
           prevents an IQ3 argmax from changing solely because the cache path
           introduced a different float accumulation order.  The order kept
           is the cache-free branch's, which is now the dot object's (on an
           AVX2 CPU it was dot_avx2's, up to 1 ULP away; ADR-0222). */
        float coefficient;
        if (!linear_zero_coefficient(query, key, beta, &coefficient))
          return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_RECURRENT);
        for (uint32_t index = 0; index < LINEAR_HEAD_DIM; index++)
          output[index] = value[index] * coefficient;
      }
    }
  }

  if (!linear->norm.data || linear->norm.type != AIUEOS_GGML_F32 ||
      linear->norm.dimension_count != 1 ||
      linear->norm.dimensions[0] != LINEAR_HEAD_DIM)
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_OUTPUT);
  const float *weights = (const float *)(const void *)linear->norm.data;
  /* The gated output norm: per head RMS * weights * silu(gate), on the norm
     object's mode 3 and the activation object's mode 4 (ADR-0222). The
     answer is in scratch_b on the live path and scratch_c on the reference;
     `gated` says which. */
  const float *gated =
      linear_output_norm(scratch_c, scratch_b, 48, LINEAR_HEAD_DIM, weights);
  if (!gated) return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_OUTPUT);

  if (!matvec(&linear->output, gated, LINEAR_INNER, normalized, EMBED))
    return fail_at(AIUEOS_QWEN35_FAILURE_LINEAR_OUTPUT);
  for (uint32_t index = 0; index < EMBED; index++) state[index] += normalized[index];
  return 1;
}

/* The de-interleave, the FUSED SOFTMAX and the position-zero reduction of
 * `full_attention`, KEPT AS THE REFERENCE and no longer the live path
 * (ADR-0220 cutover stage 3): parity profile 3 (AIUEOS_QWEN35_KOTOBA_PARITY=3)
 * compares `aiueos-qwen35-attention` against them on the CPU, and
 * `-DAIUEOS_QWEN35_C_REFERENCE_ATTENTION` makes them the forward pass again
 * for the builds that do not link that object: the host smokes and parity
 * profiles 1, 2 and 4.  The geometry (24 heads, HEAD_DIM wide, six heads per
 * KV head) arrives as arguments so the self-test can drive a smaller one.
 * ADR-0175. */
#if AIUEOS_QWEN35_KOTOBA_PARITY == 3 || defined(AIUEOS_QWEN35_C_REFERENCE_ATTENTION)
static void attention_deinterleave_c(float *out, const float *qg,
                                     uint32_t heads) {
  for (uint32_t head = 0; head < heads; head++)
    for (uint32_t index = 0; index < HEAD_DIM; index++)
      out[head * HEAD_DIM + index] = qg[head * HEAD_DIM * 2U + index];
}

static void attention_zero_position_c(float *out, const float *qg,
                                      const float *value, uint32_t heads,
                                      uint32_t group) {
  for (uint32_t head = 0; head < heads; head++) {
    uint32_t value_head = head / group;
    for (uint32_t index = 0; index < HEAD_DIM; index++) {
      float gate = qg[head * HEAD_DIM * 2U + HEAD_DIM + index];
      out[head * HEAD_DIM + index] =
          value[value_head * HEAD_DIM + index] * sigmoid(gate);
    }
  }
}

/* Zero on success, otherwise the failure stage.  `key_slot` and `value_slot`
 * are this layer's cache rows AFTER `resolved_cached_key` has run: the caller
 * resolves once per prior rather than once per (head, prior), which repairs
 * the same rows -- the repair reads the whole 1,024-float row and does not
 * depend on the KV head, and it is idempotent. */
static uint32_t attention_softmax_heads_c(float *qg, const float *query,
                                          const float *key_slot,
                                          const float *value_slot,
                                          float *weights, uint32_t heads,
                                          uint32_t group, uint32_t position) {
  for (uint32_t head = 0; head < heads; head++) {
    uint32_t kv_head = head / group;
    const float *q = query + head * HEAD_DIM;
    if (!finite_values(q, HEAD_DIM))
      return AIUEOS_QWEN35_FAILURE_FULL_QUERY;
    double attention_scores[AIUEOS_QWEN35_GENERATION_TOKENS];
    double maximum = -1.7976931348623157e+308;
    for (uint32_t prior = 0; prior <= position; prior++) {
      const float *key =
        key_slot + (uint64_t)prior * FULL_KV_WIDTH + kv_head * HEAD_DIM;
      double score;
      if (!stable_attention_score(q, key, HEAD_DIM, &score))
        return AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX;
      attention_scores[prior] = score;
      if (score > maximum) maximum = score;
    }
    float denominator = 0.0f;
    for (uint32_t prior = 0; prior <= position; prior++) {
      double difference = attention_scores[prior] - maximum;
      float shifted = difference <= -87.0 ? -87.0f :
                      difference >= 0.0 ? 0.0f : (float)difference;
      weights[prior] = local_exp(shifted);
      denominator += weights[prior];
    }
    if (!(denominator > 0.0f) || !finite_float(denominator))
      return AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX;
    float *output = qg + head * HEAD_DIM;
    for (uint32_t index = 0; index < HEAD_DIM; index++) output[index] = 0.0f;
    for (uint32_t prior = 0; prior <= position; prior++) {
      const float *value =
        value_slot + (uint64_t)prior * FULL_KV_WIDTH + kv_head * HEAD_DIM;
      float weight = weights[prior] / denominator;
      for (uint32_t index = 0; index < HEAD_DIM; index++)
        output[index] += value[index] * weight;
    }
    /* The gate is read IN PLACE.  It cannot have been overwritten: head h's
     * output occupies [h*D, (h+1)*D) and its gate begins at h*2D + D, and
     * h*2D + D >= (h+1)*D for every h >= 0, with equality only at h = 0.  The
     * staging copy this code used to make through `scratch_b` was made AFTER
     * the output was written, so it was already reading the same bytes this
     * line reads, and it moved a float without rounding it. */
    for (uint32_t index = 0; index < HEAD_DIM; index++)
      output[index] *= sigmoid(qg[head * HEAD_DIM * 2U + HEAD_DIM + index]);
  }
  return AIUEOS_QWEN35_FAILURE_NONE;
}
#endif

#if AIUEOS_QWEN35_KOTOBA_PARITY == 3 || !defined(AIUEOS_QWEN35_C_REFERENCE_ATTENTION)
extern uint64_t kotoba_aiueos_qwen35_attention(uint8_t *arena,
                                               uint64_t arena_bytes,
                                               const uint8_t *plan,
                                               uint64_t plan_bytes);
#endif

#ifdef AIUEOS_QWEN35_C_REFERENCE_ATTENTION
static int attention_deinterleave(float *out, const float *qg,
                                  uint32_t heads) {
  attention_deinterleave_c(out, qg, heads);
  return 1;
}

static int attention_zero_position(float *out, const float *qg,
                                   const float *value, uint32_t heads,
                                   uint32_t group) {
  attention_zero_position_c(out, qg, value, heads, group);
  return 1;
}

static uint32_t attention_softmax_heads(float *qg, const float *query,
                                        const float *key_slot,
                                        const float *value_slot,
                                        float *scratch, uint32_t heads,
                                        uint32_t group, uint32_t position) {
  return attention_softmax_heads_c(qg, query, key_slot, value_slot, scratch,
                                   heads, group, position);
}
#else
/* THE LIVE ATTENTION ARITHMETIC IS THE KOTOBA OBJECT (ADR-0220 cutover
 * stage 3).  The object takes ONE arena and a 96-byte plan of offsets into
 * it (its own header says why: a five-argument ABI and `kernel-subregion`'s
 * base rule).  The live regions are not one allocation -- the query/gate and
 * output live in the workspace, the key and value rows in the decode
 * context -- so the arena is the smallest span that covers every region the
 * plan names, and each offset is that region's distance from the span's
 * base.  The object bounds every region against the span, not against the
 * allocation it came from; what keeps a region inside its own allocation is
 * the extents below, which are the object's own `regions-fit` extents.
 *
 * The plan is words: slot k is byte 8k.  Word 0 is the u32 mode with the u32
 * reserved field (zero) above it.  A slot whose `extent` is non-zero holds an
 * ADDRESS until the rebase turns it into an offset; every other slot is a
 * count or stays zero, which the object demands of a slot its mode does not
 * use. */
static uint64_t attention_call(uint64_t *plan, const uint64_t *extent) {
  uint64_t low = ~0ULL, high = 0;
  for (uint32_t slot = 0; slot < 12U; slot++) {
    if (!extent[slot]) continue;
    if (plan[slot] < low) low = plan[slot];
    if (plan[slot] + extent[slot] > high) high = plan[slot] + extent[slot];
  }
  for (uint32_t slot = 0; slot < 12U; slot++)
    if (extent[slot]) plan[slot] -= low;
  return kotoba_aiueos_qwen35_attention((uint8_t *)(uintptr_t)low, high - low,
                                        (const uint8_t *)(const void *)plan,
                                        96);
}

static int attention_deinterleave(float *out, const float *qg,
                                  uint32_t heads) {
  uint64_t plan[12] = {0}, extent[12] = {0};
  plan[0] = 0;
  plan[1] = heads;
  plan[2] = HEAD_DIM;
  plan[3] = (uint64_t)(uintptr_t)out;  extent[3] = (uint64_t)heads * HEAD_DIM * 4U;
  plan[4] = (uint64_t)(uintptr_t)qg;   extent[4] = (uint64_t)heads * HEAD_DIM * 8U;
  return attention_call(plan, extent) == 0;
}

static int attention_zero_position(float *out, const float *qg,
                                   const float *value, uint32_t heads,
                                   uint32_t group) {
  uint64_t plan[12] = {0}, extent[12] = {0};
  plan[0] = 2;
  plan[1] = heads;
  plan[2] = HEAD_DIM;
  plan[3] = (uint64_t)(uintptr_t)out;   extent[3] = (uint64_t)heads * HEAD_DIM * 4U;
  plan[4] = (uint64_t)(uintptr_t)qg;    extent[4] = (uint64_t)heads * HEAD_DIM * 8U;
  plan[5] = (uint64_t)(uintptr_t)value;
  extent[5] = (uint64_t)((heads + group - 1U) / group) * HEAD_DIM * 4U;
  plan[9] = group;
  return attention_call(plan, extent) == 0;
}

/* `scratch` is 128 bytes the object owns for the call (eight binary64
 * scores, eight binary32 weights, the maximum and the denominator); the C
 * reference used the same pointer as its eight-float weight row. */
static uint32_t attention_softmax_heads(float *qg, const float *query,
                                        const float *key_slot,
                                        const float *value_slot,
                                        float *scratch, uint32_t heads,
                                        uint32_t group, uint32_t position) {
  uint64_t plan[12] = {0}, extent[12] = {0};
  uint64_t prefix = (uint64_t)(position + 1U) * FULL_KV_WIDTH * 4U;
  plan[0] = 1;
  plan[1] = heads;
  plan[2] = HEAD_DIM;
  plan[4] = (uint64_t)(uintptr_t)qg;         extent[4] = (uint64_t)heads * HEAD_DIM * 8U;
  plan[5] = (uint64_t)(uintptr_t)key_slot;   extent[5] = prefix;
  plan[6] = (uint64_t)(uintptr_t)value_slot; extent[6] = prefix;
  plan[7] = (uint64_t)(uintptr_t)query;      extent[7] = (uint64_t)heads * HEAD_DIM * 4U;
  plan[8] = FULL_KV_WIDTH;
  plan[9] = group;
  plan[10] = position;
  plan[11] = (uint64_t)(uintptr_t)scratch;   extent[11] = 128U;
  uint64_t result = attention_call(plan, extent);
  if (result == 0) return AIUEOS_QWEN35_FAILURE_NONE;
  /* -11 is the object's non-finite query, `FULL_QUERY` in the C; every
     other refusal -- a non-finite key or score, a denominator that is not
     positive and finite, or a plan it would not admit -- is the softmax. */
  return result == (uint64_t)(int64_t)-11 ? AIUEOS_QWEN35_FAILURE_FULL_QUERY
                                          : AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX;
}
#endif

static int full_attention(const struct aiueos_qwen35_layer *layer,
                          struct qwen35_decode_context *decode,
                          uint32_t full_slot) {
  const struct aiueos_qwen35_attention_tensors *full = &layer->mixer.full;
  if (!rms_norm(state, &layer->attention_norm, EMBED, normalized) ||
      !matvec(&full->query_gate, normalized, EMBED, scratch_a, FULL_QG) ||
      !matvec(&full->value, normalized, EMBED, scratch_b, FULL_VALUE))
    return fail_at(AIUEOS_QWEN35_FAILURE_ATTENTION_PROJECTION);

  if (decode) {
    /* This output must not be `dequantized`: matvec_range uses that array as
       its BSP row buffer, so every next key row would overwrite the outputs
       already computed (and race the AP half).  A one-element position-zero
       softmax masks the corruption because its weight is always one; position
       one is the first time cached keys affect a score.  Keep values, the gate
       temporary, and this key projection in three disjoint scratch_b ranges. */
    float *key_projection = scratch_b + FULL_KEY_TEMP_OFFSET;
    if (decode->position >= AIUEOS_QWEN35_GENERATION_TOKENS ||
        !matvec(&full->key, normalized, EMBED, key_projection, FULL_VALUE) ||
        !finite_values(key_projection, FULL_VALUE))
      return fail_at(AIUEOS_QWEN35_FAILURE_FULL_KEY);

    /* Remove the per-head Q/G interleave before normalization and RoPE. */
    if (!attention_deinterleave(scratch_c, scratch_a, 24) ||
        !rms_norm_heads_weighted(scratch_c, 24, HEAD_DIM,
                                 &full->query_norm) ||
        !rms_norm_heads_weighted(key_projection, 4, HEAD_DIM,
                                 &full->key_norm) ||
        !rope_heads(scratch_c, 24, decode->position) ||
        !rope_heads(key_projection, 4, decode->position))
      return fail_at(AIUEOS_QWEN35_FAILURE_FULL_KEY);

    uint64_t entry = ((uint64_t)full_slot * AIUEOS_QWEN35_GENERATION_TOKENS +
                      decode->position) * FULL_KV_WIDTH;
    float *key_entry = decode->full_key + entry;
    float *value_entry = decode->full_value + entry;
    float *shadow_entry = decode->full_key_shadow + entry;
    for (uint32_t index = 0; index < FULL_KV_WIDTH; index++) {
      key_entry[index] = key_projection[index];
      shadow_entry[index] = key_projection[index];
      value_entry[index] = scratch_b[index];
    }
    uint32_t cache_index =
      full_slot * AIUEOS_QWEN35_GENERATION_TOKENS + decode->position;
    decode->full_key_hash[cache_index] =
      float_values_hash(key_projection, FULL_KV_WIDTH);

    if (decode->position) {
      /* Resolve the causal prefix ONCE PER PRIOR rather than once per
         (head, prior): `resolved_cached_key` repairs the whole 1,024-float
         row from the shadow and its repair does not depend on the KV head. */
      for (uint32_t prior = 0; prior <= decode->position; prior++) {
        uint64_t cache_entry =
          (uint64_t)full_slot * AIUEOS_QWEN35_GENERATION_TOKENS + prior;
        if (!resolved_cached_key(decode, cache_entry, 0))
          return fail_at(AIUEOS_QWEN35_FAILURE_FULL_CACHE);
      }
      uint64_t slot_base = (uint64_t)full_slot *
        AIUEOS_QWEN35_GENERATION_TOKENS * FULL_KV_WIDTH;
      uint32_t stage =
        attention_softmax_heads(scratch_a, scratch_c,
                                decode->full_key + slot_base,
                                decode->full_value + slot_base,
                                beta_values, 24, 6, decode->position);
      if (stage != AIUEOS_QWEN35_FAILURE_NONE) return fail_at(stage);
      /* Attention output must be contiguous [24,256].  The computation above
         wrote it there in scratch_a after consuming each head's gate. */
      for (uint32_t index = 0; index < LINEAR_INNER; index++)
        scratch_c[index] = scratch_a[index];
    }
  }
  if (!decode || !decode->position) {
    /* Position zero still populates the normalized K/V cache above, but its
       emitted activation must be bit-for-bit the same reduction as the
       physically-qualified cache-free first-token path.  A one-element
       softmax is algebraically equivalent, not floating-point equivalent. */
    if (!attention_zero_position(scratch_c, scratch_a, scratch_b, 24, 6))
      return fail_at(AIUEOS_QWEN35_FAILURE_FULL_OUTPUT);
  }
  if (!matvec(&full->output, scratch_c, LINEAR_INNER, normalized, EMBED))
    return fail_at(AIUEOS_QWEN35_FAILURE_FULL_OUTPUT);
  for (uint32_t index = 0; index < EMBED; index++) state[index] += normalized[index];
  return 1;
}

struct qwen35_token_choice {
  uint32_t token;
  uint32_t second_token;
  float logit;
  float second_logit;
  uint64_t cycles;
  uint32_t failed_layer;
  uint32_t failure_stage;
};

static int inference_inputs_valid(const struct aiueos_qwen35_model *model,
                                  uint32_t input_token,
                                  const void *workspace,
                                  uint64_t workspace_bytes,
                                  uint64_t required_bytes) {
  return model && workspace && !((uintptr_t)workspace & 15U) &&
         workspace_bytes >= required_bytes &&
         model->accessible_bytes == model->artifact_bytes &&
         input_token < model->vocab_size &&
         model->artifact_bytes == AIUEOS_QWEN35_ARTIFACT_BYTES;
}

static void attach_workspace(void *workspace) {
  struct qwen35_workspace *memory = (struct qwen35_workspace *)workspace;
  state = memory->state;
  normalized = memory->normalized;
  scratch_a = memory->scratch_a;
  scratch_b = memory->scratch_b;
  scratch_c = memory->scratch_c;
  dequantized = memory->dequantized;
  ap_dequantized = memory->ap_dequantized;
  beta_values = memory->beta_values;
}

static void configure_backend(void) {
#if defined(__x86_64__) && !defined(AIUEOS_QWEN35_SCALAR)
  prepare_bsp_extended_state();
  qwen_vector_bits = !qwen_force_scalar && cpu_has_avx2() ? 256U : 0U;
#else
  qwen_vector_bits = 0U;
#endif
#ifdef AIUEOS_QWEN35_SMP
  qwen_worker_threads = aiueos_smp_worker_threads();
#else
  qwen_worker_threads = 1U;
#endif
}

/* The logits of `normalized` against the output projection, and the two
   largest of them. Zero on a malformed tensor, a refused matvec or a
   non-finite logit; the caller names the failure stage. */
static int select_output_token(const struct aiueos_qwen35_tensor *output,
                               uint32_t vocab,
                               struct qwen35_token_choice *choice) {
  choice->token = UINT32_MAX;
  choice->second_token = UINT32_MAX;
  choice->logit = -3.402823466e+38f;
  choice->second_logit = -3.402823466e+38f;
  /* The output projection goes through `matvec` -- the Kotoba object since
     ADR-0221 -- and not a per-row C `dot`. The workspace has no room for all
     vocab logits, so the tensor is walked as views of at most FFN rows (the
     same bytes with a smaller row count, so the object is told only about
     the rows it writes) and each view's logits land in scratch_a, which the
     trunk no longer needs. The selection is comparisons only, in token
     order, as before. The object's dot is `dot_scalar`'s tree; the
     `dot_avx2` this replaced on an AVX2 CPU reduces its lanes in another
     order and is up to 1 ULP away (QWEN-PARITY dot-avx2, ADR-0222). */
  uint64_t row_bytes = aiueos_qwen35_quant_row_bytes(output->type, EMBED);
  if (output->dimension_count != 2 || output->dimensions[0] != EMBED ||
      output->dimensions[1] != vocab || !row_bytes ||
      (uint64_t)vocab * row_bytes > output->storage_bytes) return 0;
  for (uint32_t first = 0; first < vocab; first += FFN) {
    uint32_t count = vocab - first < FFN ? vocab - first : FFN;
    struct aiueos_qwen35_tensor view = *output;
    view.dimensions[1] = count;
    view.data = output->data + (uint64_t)first * row_bytes;
    view.storage_bytes = (uint64_t)count * row_bytes;
    if (!matvec(&view, normalized, EMBED, scratch_a, count)) return 0;
    for (uint32_t offset = 0; offset < count; offset++) {
      uint32_t token = first + offset;
      float logit = scratch_a[offset];
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
  }
  return 1;
}

static int evaluate_token(const struct aiueos_qwen35_model *model,
                          uint32_t input_token,
                          struct qwen35_decode_context *decode,
                          aiueos_qwen35_progress_fn progress,
                          struct qwen35_token_choice *choice) {
  if (!choice) return 0;
  choice->failed_layer = 0;
  choice->failure_stage = AIUEOS_QWEN35_FAILURE_NONE;
  qwen_failure_stage = AIUEOS_QWEN35_FAILURE_NONE;
  if (!tensor_row(&model->token_embedding, input_token, state)) {
    choice->failure_stage = AIUEOS_QWEN35_FAILURE_EMBEDDING;
    return 0;
  }

  uint64_t started = read_cycles();
  uint32_t linear_slot = 0;
  uint32_t full_slot = 0;
  for (uint32_t index = 0; index < AIUEOS_QWEN35_TRUNK_LAYER_COUNT; index++) {
    const struct aiueos_qwen35_layer *layer = &model->layers[index];
    int ok = layer->linear_attention ?
      linear_attention(layer, decode, linear_slot++) :
      full_attention(layer, decode, full_slot++);
    if (!ok) {
      choice->failed_layer = index + 1U;
      choice->failure_stage = qwen_failure_stage;
      return 0;
    }
    if (!ffn(layer)) {
      choice->failed_layer = index + 1U;
      choice->failure_stage = AIUEOS_QWEN35_FAILURE_FFN;
      return 0;
    }
    if (!finite_values(state, EMBED)) {
      choice->failed_layer = index + 1U;
      choice->failure_stage = AIUEOS_QWEN35_FAILURE_STATE_NONFINITE;
      return 0;
    }
    if (progress) progress(index + 1U, AIUEOS_QWEN35_TRUNK_LAYER_COUNT, 0);
  }

  if (!rms_norm(state, &model->output_norm, EMBED, normalized) ||
      !finite_values(normalized, EMBED)) {
    choice->failure_stage = AIUEOS_QWEN35_FAILURE_OUTPUT_NORM;
    return 0;
  }
  if (progress) progress(64, 64, 1);

  if (!select_output_token(&model->output, model->vocab_size, choice)) {
    choice->failure_stage = AIUEOS_QWEN35_FAILURE_OUTPUT_LOGITS;
    return 0;
  }
  uint64_t finished = read_cycles();
  choice->cycles = finished >= started ? finished - started : 0;
  if (choice->token == UINT32_MAX || choice->second_token == UINT32_MAX) {
    choice->failure_stage = AIUEOS_QWEN35_FAILURE_OUTPUT_SELECTION;
    return 0;
  }
  return 1;
}

int aiueos_qwen35_first_token(
    const struct aiueos_qwen35_model *model,
    uint32_t input_token,
    void *workspace,
    uint64_t workspace_bytes,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_first_token_result *result) {
  if (!result || !inference_inputs_valid(
      model, input_token, workspace, workspace_bytes,
      sizeof(struct qwen35_workspace))) return 0;
  attach_workspace(workspace);
  configure_backend();
  struct qwen35_token_choice choice;
  if (!evaluate_token(model, input_token, 0, progress, &choice)) return 0;
  result->token = choice.token;
  result->second_token = choice.second_token;
  result->logit = choice.logit;
  result->second_logit = choice.second_logit;
  result->compute_cycles = choice.cycles;
  result->vector_bits = qwen_vector_bits;
  result->worker_threads = qwen_worker_threads;
  return 1;
}

static void zero_bytes(void *memory, uint64_t count) {
  uint8_t *bytes = (uint8_t *)memory;
  for (uint64_t index = 0; index < count; index++) bytes[index] = 0;
}

int aiueos_qwen35_generate(
    const struct aiueos_qwen35_model *model,
    uint32_t input_token,
    uint32_t generated_tokens,
    void *workspace,
    uint64_t workspace_bytes,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_generation_result *result) {
  if (!result || generated_tokens < 2U ||
      generated_tokens > AIUEOS_QWEN35_GENERATION_TOKENS ||
      !inference_inputs_valid(model, input_token, workspace, workspace_bytes,
                              AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES))
    return 0;
  attach_workspace(workspace);
  configure_backend();

  uint8_t *decode_memory =
    (uint8_t *)workspace + AIUEOS_QWEN35_WORKSPACE_BYTES;
  zero_bytes(decode_memory,
             AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES -
             AIUEOS_QWEN35_WORKSPACE_BYTES);
  struct qwen35_decode_context decode = {
    .recurrent = (float *)(void *)decode_memory,
    .conv = (float *)(void *)(decode_memory + AIUEOS_QWEN35_RECURRENT_BYTES),
    .full_key = (float *)(void *)(decode_memory +
      AIUEOS_QWEN35_RECURRENT_BYTES + AIUEOS_QWEN35_CONV_STATE_BYTES),
    .full_value = (float *)(void *)(decode_memory +
      AIUEOS_QWEN35_RECURRENT_BYTES + AIUEOS_QWEN35_CONV_STATE_BYTES +
      AIUEOS_QWEN35_FULL_CACHE_PLANE_BYTES),
    .full_key_shadow = (float *)(void *)(decode_memory +
      AIUEOS_QWEN35_RECURRENT_BYTES + AIUEOS_QWEN35_CONV_STATE_BYTES +
      2U * AIUEOS_QWEN35_FULL_CACHE_PLANE_BYTES),
    .full_key_hash = (uint64_t *)(void *)(decode_memory +
      AIUEOS_QWEN35_RECURRENT_BYTES + AIUEOS_QWEN35_CONV_STATE_BYTES +
      3U * AIUEOS_QWEN35_FULL_CACHE_PLANE_BYTES),
    .position = 0
  };

  result->generated_tokens = 0;
  result->decode_tokens = 0;
  result->first_token_cycles = 0;
  result->decode_cycles = 0;
  result->total_cycles = 0;
  result->vector_bits = qwen_vector_bits;
  result->worker_threads = qwen_worker_threads;
  result->failed_token = 0;
  result->failed_layer = 0;
  result->failure_stage = AIUEOS_QWEN35_FAILURE_NONE;

  uint32_t current_input = input_token;
  for (uint32_t position = 0; position < generated_tokens; position++) {
    struct qwen35_token_choice choice;
    decode.position = position;
    if (progress) progress(position + 1U, generated_tokens, 3);
    if (!evaluate_token(model, current_input, &decode, progress, &choice)) {
      result->failed_token = position + 1U;
      result->failed_layer = choice.failed_layer;
      result->failure_stage = choice.failure_stage;
      return 0;
    }
    result->tokens[position] = choice.token;
    result->generated_tokens++;
    result->total_cycles += choice.cycles;
    if (!position) {
      result->first_token_cycles = choice.cycles;
      if (choice.token != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN) {
        result->failed_token = 1U;
        /* The output head is outside the trunk, so this field carries the
           observed token for the bounded physical failure report. */
        result->failed_layer = choice.token;
        result->failure_stage = AIUEOS_QWEN35_FAILURE_REFERENCE_TOKEN;
        return 0;
      }
    } else {
      result->decode_cycles += choice.cycles;
      result->decode_tokens++;
    }
    if (progress) progress(position + 1U, generated_tokens, 2);
    current_input = choice.token;
  }
  return result->generated_tokens == generated_tokens &&
         result->decode_tokens == generated_tokens - 1U;
}

#ifdef AIUEOS_QWEN35_TESTING
/* The output projection's selection over a caller-built tensor: `input` is
   the normalized state, `logits` and `row` are FFN floats of scratch. */
int aiueos_qwen35_test_output_select(
    const struct aiueos_qwen35_tensor *output, uint32_t vocab,
    float *input, float *logits, float *row,
    uint32_t *token, uint32_t *second_token,
    float *logit, float *second_logit) {
  struct qwen35_token_choice choice;
  normalized = input;
  scratch_a = logits;
  dequantized = row;
  if (!select_output_token(output, vocab, &choice)) return 0;
  *token = choice.token;
  *second_token = choice.second_token;
  *logit = choice.logit;
  *second_logit = choice.second_logit;
  return 1;
}

float aiueos_qwen35_test_softplus(float value) {
  return softplus(value);
}

void aiueos_qwen35_test_rope(float values[HEAD_DIM], uint32_t position) {
  (void)rope_heads(values, 1, position);
}

void aiueos_qwen35_test_recurrent_step(
    float state_values[LINEAR_HEAD_DIM * LINEAR_HEAD_DIM],
    const float key[LINEAR_HEAD_DIM],
    const float query[LINEAR_HEAD_DIM],
    const float value[LINEAR_HEAD_DIM],
    float decay, float beta,
    float correction[LINEAR_HEAD_DIM],
    float output[LINEAR_HEAD_DIM]) {
  recurrent_step(state_values, key, query, value, decay, beta,
                 correction, output);
}

uint32_t aiueos_qwen35_test_linear_key_head(uint32_t value_head) {
  return value_head / LINEAR_KV_GROUP_SIZE;
}

int aiueos_qwen35_test_attention_score(
    const float query[HEAD_DIM], const float key[HEAD_DIM], double *score) {
  return stable_attention_score(query, key, HEAD_DIM, score);
}

uint64_t aiueos_qwen35_test_cache_hash(const float values[FULL_KV_WIDTH]) {
  return float_values_hash(values, FULL_KV_WIDTH);
}

int aiueos_qwen35_test_cache_resolve(
    float primary[FULL_KV_WIDTH], float shadow[FULL_KV_WIDTH],
    uint64_t expected_hash) {
  struct qwen35_decode_context decode = {
    .full_key = primary,
    .full_key_shadow = shadow,
    .full_key_hash = &expected_hash
  };
  return resolved_cached_key(&decode, 0, 0) == primary;
}

#endif

/* ── QWEN-PARITY: the Kotoba objects against this file, on the CPU ─────────
 *
 * ADR-0147.  `aiueos-qwen35-dequant-row`, `aiueos-qwen35-dot-f32` and
 * `aiueos-qwen35-matvec` are ports of `aiueos_qwen35_dequantize_row`,
 * `dot_scalar` and `matvec_range`.  Their contracts are checked against a
 * ClojureScript re-derivation in the KIR interpreter, which proves the
 * ALGORITHM and says nothing about what amu emitted.  This runs the emitted
 * objects on the target and compares every bit against the C that is compiled
 * beside them -- the only evidence that covers the backend too, and the same
 * argument `AIUEOS_X25519_OK` makes in main.c.
 *
 * The inputs are synthetic and deterministic (xorshift32), not the model: this
 * has to run in the plain UEFI smoke, where no 10.9 GiB mapping exists.  What
 * it establishes is bit-equality of the arithmetic, which is the property the
 * model path needs and the one a wrong nibble, a wrong scale index or a
 * different accumulation tree breaks.
 *
 * Prints one line per stage on the serial port, `QWEN-PARITY <stage> ok` or
 * `... mismatch`, and returns zero on the first disagreement.
 */
#ifdef AIUEOS_QWEN35_KOTOBA_PARITY

/* TWO PROFILES, AND THE REASON IS THE LINKER SCRIPT.
 * `aiueos_low_end <= 0x1f4000` leaves 999,424 bytes for text, rodata,
 * data and bss together, and since the tokenizer objects landed there is
 * less headroom than these five objects need at once (measured: adding the
 * 16,120 bytes of `qwen35-activation.o` + `qwen35-norm.o` to a link that
 * already carries the other three overflows it). So the comparison runs in
 * two halves, each linking only the objects its stages call:
 *
 *   AIUEOS_QWEN35_KOTOBA_PARITY=1   dequant, dot, matvec
 *   AIUEOS_QWEN35_KOTOBA_PARITY=2   activation, norm
 *
 * Splitting the RUN rather than the evidence: both halves are the emitted
 * objects against the compiled C on the same CPU, and neither half is
 * weaker for the other one not being linked beside it. */
static uint32_t qwen_parity_state;

static uint8_t qwen_parity_byte(void) {
  uint32_t x = qwen_parity_state;
  x ^= x << 13; x ^= x >> 17; x ^= x << 5;
  qwen_parity_state = x;
  return (uint8_t)(x & 0xffU);
}

/* A spread of magnitudes rather than a spread of mantissas: the accumulation
   tree is what is being compared, and a tree only shows itself when the
   addends round differently depending on the order they arrive in. */
static float qwen_parity_value(void) {
  int32_t mantissa = (int32_t)qwen_parity_byte() - 128;
  int32_t exponent = (int32_t)(qwen_parity_byte() & 15U) - 7;
  float value = (float)mantissa;
  for (int32_t step = 0; step < exponent; step++) value *= 2.0f;
  for (int32_t step = exponent; step < 0; step++) value *= 0.5f;
  return value;
}

static uint32_t qwen_parity_bits(float value) {
  union { float value; uint32_t bits; } representation = {value};
  return representation.bits;
}

static void qwen_parity_write_u32(uint8_t *plan, uint32_t offset, uint32_t v) {
  plan[offset + 0] = (uint8_t)(v & 0xffU);
  plan[offset + 1] = (uint8_t)((v >> 8) & 0xffU);
  plan[offset + 2] = (uint8_t)((v >> 16) & 0xffU);
  plan[offset + 3] = (uint8_t)((v >> 24) & 0xffU);
}

static void qwen_parity_write_u64(uint8_t *plan, uint32_t offset, uint64_t v) {
  qwen_parity_write_u32(plan, offset, (uint32_t)(v & 0xffffffffU));
  qwen_parity_write_u32(plan, offset + 4, (uint32_t)(v >> 32));
}


#if AIUEOS_QWEN35_KOTOBA_PARITY == 1

#define QWEN_PARITY_COLS 256U
#define QWEN_PARITY_ROWS 4U
#define QWEN_PARITY_MAX_ROW_BYTES 1024U

static uint64_t qwen_parity_row_bytes(uint32_t type) {
  return aiueos_qwen35_quant_row_bytes(type, QWEN_PARITY_COLS);
}

/* [weights][input][output][row scratch] in one region, which is what
   `aiueos-qwen35-matvec` takes: `kernel-subregion` requires a BASE to be a
   parameter, so four regions cannot arrive as four bases through a five-
   argument ABI. */
static uint8_t __attribute__((section(".high_bss"), aligned(8))) qwen_parity_arena[
    QWEN_PARITY_ROWS * QWEN_PARITY_MAX_ROW_BYTES
    + QWEN_PARITY_COLS * 4U + QWEN_PARITY_ROWS * 4U + QWEN_PARITY_COLS * 4U];
static uint8_t __attribute__((section(".high_bss"), aligned(8))) qwen_parity_plan[96];
static float __attribute__((section(".high_bss"))) qwen_parity_reference_row[QWEN_PARITY_COLS];
static float __attribute__((section(".high_bss"))) qwen_parity_object_row[QWEN_PARITY_COLS];
static float __attribute__((section(".high_bss"))) qwen_parity_reference_out[QWEN_PARITY_ROWS];

/* F32, Q8_0, Q4_K, Q6_K -- the four this object decodes.  The IQ types stay in
   the C for want of a rodata facility to hold their codebook grids. */
/* Every tensor type the admitted artifact holds (ADR-0221). Until then the
   four whose equations need no codebook; the object decodes all fifteen now,
   and the ones that dominate the model (IQ3_XXS, IQ3_S, IQ4_XS, IQ2_S) are
   exactly the ones this self-test could not reach before. */
#define QWEN_PARITY_TYPE_COUNT 15U
static const uint32_t qwen_parity_types[QWEN_PARITY_TYPE_COUNT] = {
  AIUEOS_GGML_F32, AIUEOS_GGML_Q8_0, AIUEOS_GGML_Q2_K, AIUEOS_GGML_Q3_K,
  AIUEOS_GGML_Q4_K, AIUEOS_GGML_Q5_K, AIUEOS_GGML_Q6_K,
  AIUEOS_GGML_IQ2_XXS, AIUEOS_GGML_IQ2_XS, AIUEOS_GGML_IQ3_XXS,
  AIUEOS_GGML_IQ1_S, AIUEOS_GGML_IQ3_S, AIUEOS_GGML_IQ2_S,
  AIUEOS_GGML_IQ4_XS, AIUEOS_GGML_IQ1_M
};

static int qwen_parity_dequant(uint32_t type) {
  uint64_t row_bytes = qwen_parity_row_bytes(type);
  if (!row_bytes || row_bytes > QWEN_PARITY_MAX_ROW_BYTES) return 0;
  qwen_parity_state = 0x1234567u + type;
  for (uint64_t index = 0; index < row_bytes; index++)
    qwen_parity_arena[index] = qwen_parity_byte();
  if (!aiueos_qwen35_dequantize_row(type, qwen_parity_arena,
                                    QWEN_PARITY_COLS,
                                    qwen_parity_reference_row))
    return 0;
  for (uint32_t index = 0; index < QWEN_PARITY_COLS; index++)
    qwen_parity_object_row[index] = 0.0f;
  if (kotoba_aiueos_qwen35_dequant_row(type, qwen_parity_arena, row_bytes,
                                       qwen_parity_object_row,
                                       QWEN_PARITY_COLS * 4U) != 0)
    return 0;
  for (uint32_t index = 0; index < QWEN_PARITY_COLS; index++)
    if (qwen_parity_bits(qwen_parity_reference_row[index]) !=
        qwen_parity_bits(qwen_parity_object_row[index]))
      return 0;
  return 1;
}

/* Counts 0..17 and 4096: every residue of four (dot_scalar's accumulator
   step) and of eight (the tree `kernel-dot-f32` would use if the SIMD swap-in
   were wired), plus one long vector so a per-lane divergence has room to
   show. */
static int qwen_parity_dot(void) {
  float *left = (float *)(void *)qwen_parity_arena;
  float *right = left + QWEN_PARITY_COLS;
  qwen_parity_state = 0x2468aceu;
  for (uint32_t index = 0; index < QWEN_PARITY_COLS; index++) {
    left[index] = qwen_parity_value();
    right[index] = qwen_parity_value();
  }
  for (uint32_t count = 0; count <= 17U; count++) {
    uint64_t object = kotoba_aiueos_qwen35_dot_f32(left, count * 4U, right,
                                                   count * 4U, count);
    if (object != (uint64_t)(int64_t)(int32_t)
        qwen_parity_bits(dot_scalar(left, right, count)))
      return 0;
  }
  {
    uint64_t object = kotoba_aiueos_qwen35_dot_f32(
        left, QWEN_PARITY_COLS * 4U, right, QWEN_PARITY_COLS * 4U,
        QWEN_PARITY_COLS);
    if (object != (uint64_t)(int64_t)(int32_t)
        qwen_parity_bits(dot_scalar(left, right, QWEN_PARITY_COLS)))
      return 0;
  }
  /* The refusals, so the object is not merely believed to compute. */
  if (kotoba_aiueos_qwen35_dot_f32(left, 12, right, 16, 4) !=
      (uint64_t)(int64_t)-4294967299LL) return 0;
  if (kotoba_aiueos_qwen35_dot_f32(left, 16, right, 12, 4) !=
      (uint64_t)(int64_t)-4294967300LL) return 0;
  /* `linear_attention`'s position-zero / cache-free coefficient: the live
     wrapper (the object, with the forward pass's byte counts and geometry)
     against its C twin, over nine query/key windows and nine betas. */
  typedef char qwen_parity_linear_fits[
      (LINEAR_HEAD_DIM + 128U <= QWEN_PARITY_COLS) ? 1 : -1];
  for (uint32_t offset = 0; offset <= 128U; offset += 16U) {
    float beta = qwen_parity_value();
    float live = 0.0f;
    if (!linear_zero_coefficient(left + offset, right + offset, beta, &live))
      return 0;
    if (qwen_parity_bits(live) != qwen_parity_bits(
            linear_zero_coefficient_c(left + offset, right + offset, beta)))
      return 0;
  }
  return 1;
}

/* The object's dot against the C `dot_avx2` -- the path `dot` took on an
   AVX2 CPU, and the one the output projection took until it moved to the
   matvec object. `qwen_parity_dot` above holds the object to `dot_scalar`.
   AVX2 is NOT the same tree (measured, ADR-0222): its lanes are the scalar
   accumulators, but it reduces them left to right, ((s0+s1)+s2)+s3, where
   the scalar does (s0+s1)+(s2+s3), and below eight elements it adds every
   product sequentially. So this is a MEASUREMENT, printed by main.c as a
   distance, like the rope's -- not a pass/fail. Returns 1 when measured,
   2 when this CPU (or an AIUEOS_QWEN35_SCALAR build) has no AVX2, which
   main.c prints as `unavailable`. */
#define QWEN_PARITY_DOT_LONG 768U
int aiueos_qwen35_parity_dot_avx2(uint32_t *compared, uint32_t *differing,
                                  uint32_t *max_ulp) {
  *compared = 0;
  *differing = 0;
  *max_ulp = 0;
#if defined(__x86_64__) && !defined(AIUEOS_QWEN35_SCALAR)
  typedef char qwen_parity_dot_long_fits[
      (2U * QWEN_PARITY_DOT_LONG * 4U <= sizeof qwen_parity_arena) ? 1 : -1];
  prepare_bsp_extended_state();
  if (!cpu_has_avx2()) return 2;
  float *left = (float *)(void *)qwen_parity_arena;
  float *right = left + QWEN_PARITY_DOT_LONG;
  qwen_parity_state = 0x13579bdu;
  for (uint32_t index = 0; index < QWEN_PARITY_DOT_LONG; index++) {
    left[index] = qwen_parity_value();
    right[index] = qwen_parity_value();
  }
  for (uint32_t count = 0; count <= QWEN_PARITY_DOT_LONG; count++) {
    if (count > 17U && count % 64U != 0U) continue;
    uint64_t object = kotoba_aiueos_qwen35_dot_f32(left, count * 4U, right,
                                                   count * 4U, count);
    uint32_t a = (uint32_t)object;
    uint32_t b = qwen_parity_bits(dot_avx2(left, right, count));
    /* ordered integers: a float's bits, with the negative half flipped so
       adjacent floats are adjacent integers across zero */
    int64_t oa = (a & 0x80000000U) ? -(int64_t)(a & 0x7fffffffU) : (int64_t)a;
    int64_t ob = (b & 0x80000000U) ? -(int64_t)(b & 0x7fffffffU) : (int64_t)b;
    int64_t gap = oa > ob ? oa - ob : ob - oa;
    if (object != (uint64_t)(int64_t)(int32_t)a) return 0;
    (*compared)++;
    if (gap) {
      (*differing)++;
      if (gap > (int64_t)*max_ulp)
        *max_ulp = gap > 0xffffffffLL ? 0xffffffffU : (uint32_t)gap;
    }
  }
  return 1;
#else
  return 2;
#endif
}

static int qwen_parity_matvec(uint32_t type) {
  uint64_t row_bytes = qwen_parity_row_bytes(type);
  uint64_t weights_bytes = row_bytes * QWEN_PARITY_ROWS;
  uint64_t input_offset = weights_bytes;
  uint64_t output_offset = input_offset + QWEN_PARITY_COLS * 4U;
  uint64_t scratch_offset = output_offset + QWEN_PARITY_ROWS * 4U;
  uint64_t arena_bytes = scratch_offset + QWEN_PARITY_COLS * 4U;
  float *input;
  struct aiueos_qwen35_tensor tensor;
  if (!row_bytes || row_bytes > QWEN_PARITY_MAX_ROW_BYTES) return 0;
  if (arena_bytes > sizeof qwen_parity_arena) return 0;
  qwen_parity_state = 0x9abcdefu + type;
  for (uint64_t index = 0; index < weights_bytes; index++)
    qwen_parity_arena[index] = qwen_parity_byte();
  input = (float *)(void *)(qwen_parity_arena + input_offset);
  for (uint32_t index = 0; index < QWEN_PARITY_COLS; index++)
    input[index] = qwen_parity_value();
  for (uint64_t index = output_offset; index < arena_bytes; index++)
    qwen_parity_arena[index] = 0;

  tensor.dimensions[0] = QWEN_PARITY_COLS;
  tensor.dimensions[1] = QWEN_PARITY_ROWS;
  tensor.dimensions[2] = 0;
  tensor.dimensions[3] = 0;
  tensor.offset = 0;
  tensor.storage_bytes = weights_bytes;
  tensor.dimension_count = 2;
  tensor.type = type;
  tensor.data = qwen_parity_arena;
  if (!matvec_range_c(&tensor, input, QWEN_PARITY_COLS,
                      qwen_parity_reference_out, 0, QWEN_PARITY_ROWS,
                      qwen_parity_reference_row))
    return 0;

  for (uint32_t index = 0; index < 96U; index++) qwen_parity_plan[index] = 0;
  qwen_parity_write_u32(qwen_parity_plan, 0, type);
  qwen_parity_write_u64(qwen_parity_plan, 8, QWEN_PARITY_ROWS);
  qwen_parity_write_u64(qwen_parity_plan, 16, QWEN_PARITY_COLS);
  qwen_parity_write_u64(qwen_parity_plan, 24, 0);
  qwen_parity_write_u64(qwen_parity_plan, 32, weights_bytes);
  qwen_parity_write_u64(qwen_parity_plan, 40, input_offset);
  qwen_parity_write_u64(qwen_parity_plan, 48, output_offset);
  qwen_parity_write_u64(qwen_parity_plan, 56, scratch_offset);
  qwen_parity_write_u64(qwen_parity_plan, 64, 0);
  qwen_parity_write_u64(qwen_parity_plan, 72, QWEN_PARITY_ROWS);
  if (kotoba_aiueos_qwen35_matvec(qwen_parity_arena, arena_bytes,
                                  qwen_parity_plan, 96) != 0)
    return 0;
  {
    const float *object = (const float *)(const void *)
        (qwen_parity_arena + output_offset);
    for (uint32_t row = 0; row < QWEN_PARITY_ROWS; row++)
      if (qwen_parity_bits(qwen_parity_reference_out[row]) !=
          qwen_parity_bits(object[row]))
        return 0;
  }
  /* A plan the object must refuse: a reserved slot that is not zero.  A
     self-test that only ever sees agreement has not shown the object
     discriminates. */
  qwen_parity_write_u32(qwen_parity_plan, 4, 1);
  if (kotoba_aiueos_qwen35_matvec(qwen_parity_arena, arena_bytes,
                                  qwen_parity_plan, 96) !=
      (uint64_t)(int64_t)-4)
    return 0;
  return 1;
}


#endif /* AIUEOS_QWEN35_KOTOBA_PARITY == 1 */

#if AIUEOS_QWEN35_KOTOBA_PARITY == 2

/* Stage 3: the elementwise activations.  Every one of `local_exp`'s clamp
   boundaries is a probe value, because the clamps are where a port drifts:
   -87 returns zero, +88 saturates, and +-20 switch softplus between its three
   branches. */
#define QWEN_PARITY_ACT 128U

static float __attribute__((section(".high_bss"))) qwen_parity_act_in[QWEN_PARITY_ACT];
static float __attribute__((section(".high_bss"))) qwen_parity_act_ref[QWEN_PARITY_ACT];
static float __attribute__((section(".high_bss"))) qwen_parity_act_obj[QWEN_PARITY_ACT];
static float __attribute__((section(".high_bss"))) qwen_parity_act_gate[QWEN_PARITY_ACT];
static float __attribute__((section(".high_bss"))) qwen_parity_conv_kernel[QWEN_PARITY_ACT * 4U];
static float __attribute__((section(".high_bss"))) qwen_parity_conv_ref_h[QWEN_PARITY_ACT * LINEAR_CONV_HISTORY];
static float __attribute__((section(".high_bss"))) qwen_parity_conv_obj_h[QWEN_PARITY_ACT * LINEAR_CONV_HISTORY];

static const float qwen_parity_edges[16] = {
  0.0f, 1.0f, -1.0f, 20.0f, -20.0f, 20.5f, -20.5f, 87.0f,
  -87.0f, 88.0f, -88.0f, 89.0f, -89.0f, 0.001f, -0.001f, 12.0f
};

static int qwen_parity_activation(void) {
  uint32_t index;
  qwen_parity_state = 0x5a5a5a5u;
  for (index = 0; index < QWEN_PARITY_ACT; index++)
    qwen_parity_act_in[index] = index < 16U ? qwen_parity_edges[index]
                                            : qwen_parity_value();
  for (uint32_t mode = 0; mode < 5U; mode++) {
    for (index = 0; index < QWEN_PARITY_ACT; index++) {
      float x = qwen_parity_act_in[index];
      qwen_parity_act_obj[index] = x;
      qwen_parity_act_gate[index] = (float)((int32_t)index - 64) * 0.125f;
      qwen_parity_act_ref[index] =
        mode == 0U ? silu(x) :
        mode == 1U ? sigmoid(x) :
        mode == 2U ? softplus(x) :
        mode == 3U ? local_exp(x) :
                     silu(x) * qwen_parity_act_gate[index];
    }
    /* Through `activate`, the forward pass's own entry to the object, so
       what is compared is the live call and not a second one beside it. */
    if (!activate(mode, qwen_parity_act_obj, qwen_parity_act_gate,
                  QWEN_PARITY_ACT))
      return 0;
    for (index = 0; index < QWEN_PARITY_ACT; index++)
      if (qwen_parity_bits(qwen_parity_act_ref[index]) !=
          qwen_parity_bits(qwen_parity_act_obj[index]))
        return 0;
  }
  /* Modes 5 and 6, `linear_attention`'s conv, through `conv4` against
     `conv4_c`: a token without a cache, the first token with one, and three
     later tokens, so the history the object shifted is the history it then
     reads. Values and history are compared after every token. */
  for (index = 0; index < QWEN_PARITY_ACT * 4U; index++)
    qwen_parity_conv_kernel[index] = qwen_parity_value();
  for (index = 0; index < QWEN_PARITY_ACT * LINEAR_CONV_HISTORY; index++) {
    qwen_parity_conv_ref_h[index] = qwen_parity_value();
    qwen_parity_conv_obj_h[index] = qwen_parity_conv_ref_h[index];
  }
  for (uint32_t token = 0; token < 5U; token++) {
    int cached = token != 0U;
    uint64_t position = token > 1U ? token : 0U;
    for (index = 0; index < QWEN_PARITY_ACT; index++) {
      float x = qwen_parity_value();
      qwen_parity_act_ref[index] = x;
      qwen_parity_act_obj[index] = x;
    }
    conv4_c(qwen_parity_act_ref, qwen_parity_conv_kernel,
            cached ? qwen_parity_conv_ref_h : 0, position, QWEN_PARITY_ACT);
    if (!conv4(qwen_parity_act_obj, qwen_parity_conv_kernel,
               cached ? qwen_parity_conv_obj_h : 0, position, QWEN_PARITY_ACT))
      return 0;
    for (index = 0; index < QWEN_PARITY_ACT; index++)
      if (qwen_parity_bits(qwen_parity_act_ref[index]) !=
          qwen_parity_bits(qwen_parity_act_obj[index]))
        return 0;
    for (index = 0; index < QWEN_PARITY_ACT * LINEAR_CONV_HISTORY; index++)
      if (qwen_parity_bits(qwen_parity_conv_ref_h[index]) !=
          qwen_parity_bits(qwen_parity_conv_obj_h[index]))
        return 0;
  }
  /* Refusals, so the object is not merely believed to compute. */
  if (kotoba_aiueos_qwen35_activation(7, qwen_parity_act_obj,
                                      qwen_parity_act_gate,
                                      QWEN_PARITY_ACT, 0) != (uint64_t)(int64_t)-2)
    return 0;
  if (kotoba_aiueos_qwen35_activation(QWEN_ACT_CONV4_NEXT, qwen_parity_act_obj,
                                      qwen_parity_conv_kernel,
                                      QWEN_PARITY_ACT, 0) != (uint64_t)(int64_t)-5)
    return 0;
  return 1;
}

/* Stage 4: the four normalisations.  The reference is this file's own
   `rms_norm`, `l2_norm_heads` and `rms_norm_heads_weighted`, which reduce in
   f64 over f32 squares and narrow at different points -- the property the port
   is most likely to get subtly wrong. */
#define QWEN_PARITY_NORM_HEADS 4U
#define QWEN_PARITY_NORM_WIDTH 32U
#define QWEN_PARITY_NORM (QWEN_PARITY_NORM_HEADS * QWEN_PARITY_NORM_WIDTH)

static float __attribute__((section(".high_bss"))) qwen_parity_norm_in[QWEN_PARITY_NORM];
static float __attribute__((section(".high_bss"))) qwen_parity_norm_ref[QWEN_PARITY_NORM];
static float __attribute__((section(".high_bss"))) qwen_parity_norm_obj[QWEN_PARITY_NORM];
static float __attribute__((section(".high_bss"))) qwen_parity_norm_w[QWEN_PARITY_NORM];
static float __attribute__((section(".high_bss"))) qwen_parity_norm_gate[QWEN_PARITY_NORM];

static void qwen_parity_norm_fill(uint32_t seed) {
  qwen_parity_state = seed;
  for (uint32_t index = 0; index < QWEN_PARITY_NORM; index++) {
    qwen_parity_norm_in[index] = qwen_parity_value();
    qwen_parity_norm_w[index] = qwen_parity_value();
  }
}

static int qwen_parity_norm(void) {
  struct aiueos_qwen35_tensor weights;
  uint32_t index;
  qwen_parity_norm_fill(0x7654321u);
  weights.dimensions[0] = QWEN_PARITY_NORM;
  weights.dimensions[1] = 0;
  weights.dimensions[2] = 0;
  weights.dimensions[3] = 0;
  weights.offset = 0;
  weights.storage_bytes = QWEN_PARITY_NORM * sizeof(float);
  weights.dimension_count = 1;
  weights.type = AIUEOS_GGML_F32;
  weights.data = (const uint8_t *)(const void *)qwen_parity_norm_w;

  /* mode 0: rms_norm, out of place. */
  if (!rms_norm_c(qwen_parity_norm_in, &weights, QWEN_PARITY_NORM,
                qwen_parity_norm_ref))
    return 0;
  for (index = 0; index < QWEN_PARITY_NORM; index++)
    qwen_parity_norm_obj[index] = 0.0f;
  /* Through the live `rms_norm`, whose object call is
     `[mode input weights count output]` -- the object's own order. Getting
     this wrong is not a crash: it computes a norm of the wrong vector into the
     wrong place and every bound still holds. Measured 2026-09-02 under QEMU,
     where an earlier draft of this harness passed the output buffer as the
     input and the comparison said `norm mismatch`. Since the cutover the
     three norms below are called the way the forward pass calls them, so the
     order being checked is the live one. */
  if (!rms_norm(qwen_parity_norm_in, &weights, QWEN_PARITY_NORM,
                qwen_parity_norm_obj))
    return 0;
  for (index = 0; index < QWEN_PARITY_NORM; index++)
    if (qwen_parity_bits(qwen_parity_norm_ref[index]) !=
        qwen_parity_bits(qwen_parity_norm_obj[index]))
      return 0;

  /* mode 1: l2_norm_heads, in place. */
  qwen_parity_norm_fill(0x1111111u);
  for (index = 0; index < QWEN_PARITY_NORM; index++) {
    qwen_parity_norm_ref[index] = qwen_parity_norm_in[index];
    qwen_parity_norm_obj[index] = qwen_parity_norm_in[index];
  }
  l2_norm_heads_c(qwen_parity_norm_ref, QWEN_PARITY_NORM_HEADS,
                QWEN_PARITY_NORM_WIDTH);
  if (!l2_norm_heads(qwen_parity_norm_obj, QWEN_PARITY_NORM_HEADS,
                     QWEN_PARITY_NORM_WIDTH))
    return 0;
  for (index = 0; index < QWEN_PARITY_NORM; index++)
    if (qwen_parity_bits(qwen_parity_norm_ref[index]) !=
        qwen_parity_bits(qwen_parity_norm_obj[index]))
      return 0;

  /* mode 2: rms_norm_heads_weighted, in place, one weight row per head. */
  qwen_parity_norm_fill(0x2222222u);
  for (index = 0; index < QWEN_PARITY_NORM; index++) {
    qwen_parity_norm_ref[index] = qwen_parity_norm_in[index];
    qwen_parity_norm_obj[index] = qwen_parity_norm_in[index];
  }
  weights.dimensions[0] = QWEN_PARITY_NORM_WIDTH;
  weights.storage_bytes = QWEN_PARITY_NORM_WIDTH * sizeof(float);
  if (!rms_norm_heads_weighted_c(qwen_parity_norm_ref, QWEN_PARITY_NORM_HEADS,
                               QWEN_PARITY_NORM_WIDTH, &weights))
    return 0;
  if (!rms_norm_heads_weighted(qwen_parity_norm_obj, QWEN_PARITY_NORM_HEADS,
                               QWEN_PARITY_NORM_WIDTH, &weights))
    return 0;
  for (index = 0; index < QWEN_PARITY_NORM; index++)
    if (qwen_parity_bits(qwen_parity_norm_ref[index]) !=
        qwen_parity_bits(qwen_parity_norm_obj[index]))
      return 0;

  /* mode 3 + activation mode 4: `linear_attention`'s gated output norm,
     against `linear_output_norm_c`.  The live answer lands in the gate
     buffer, the reference's in its values; `in` becomes the reference's
     copy of the gate once the values are copied out of it. */
  qwen_parity_norm_fill(0x3333333u);
  for (index = 0; index < QWEN_PARITY_NORM; index++) {
    qwen_parity_norm_ref[index] = qwen_parity_norm_in[index];
    qwen_parity_norm_obj[index] = qwen_parity_norm_in[index];
    qwen_parity_norm_gate[index] = qwen_parity_value();
    qwen_parity_norm_in[index] = qwen_parity_norm_gate[index];
  }
  linear_output_norm_c(qwen_parity_norm_ref, qwen_parity_norm_in,
                       QWEN_PARITY_NORM_HEADS, QWEN_PARITY_NORM_WIDTH,
                       qwen_parity_norm_w);
  if (linear_output_norm(qwen_parity_norm_obj, qwen_parity_norm_gate,
                         QWEN_PARITY_NORM_HEADS, QWEN_PARITY_NORM_WIDTH,
                         qwen_parity_norm_w) != qwen_parity_norm_gate)
    return 0;
  for (index = 0; index < QWEN_PARITY_NORM; index++)
    if (qwen_parity_bits(qwen_parity_norm_ref[index]) !=
        qwen_parity_bits(qwen_parity_norm_gate[index]))
      return 0;

  /* A refusal: mode 4 does not exist. */
  if (kotoba_aiueos_qwen35_norm(4, (uint64_t)(uintptr_t)qwen_parity_norm_obj,
                                1, 8, 0) != (uint64_t)(int64_t)-2)
    return 0;
  return 1;
}

#endif /* AIUEOS_QWEN35_KOTOBA_PARITY == 2 */

#if AIUEOS_QWEN35_KOTOBA_PARITY >= 3

/* Stage 5 and stage 6: the two loops the matvecs sit between.  A THIRD
 * profile for the reason the second one exists -- `aiueos_low_end <= 0x1f4000`
 * cannot hold every object at once since the tokenizer landed -- and a stage a
 * profile did not compile is REFUSED, never reported ok.
 *
 * TWO profiles rather than one, and the number is MEASURED: the two objects
 * are 17,872 and 7,432 bytes and linking both at once overflows
 * `aiueos_low_end <= 0x1f4000` -- ld.lld says "low kernel/user layout overlaps
 * process-private aperture" and produces nothing.  Profile 2's pair is 16,120
 * bytes and fits, so the ceiling is between the two and this is not a margin
 * that can be assumed away. */

#define QWEN_ATT_HEADS 8U
#define QWEN_ATT_GROUP 2U
#define QWEN_ATT_KV_HEADS (QWEN_ATT_HEADS / QWEN_ATT_GROUP)
#define QWEN_ATT_POSITION 5U
#define QWEN_ATT_PRIORS (QWEN_ATT_POSITION + 1U)
#define QWEN_REC_DIM LINEAR_HEAD_DIM

/* One region, because that is what `kernel-subregion`'s provenance rule
 * leaves: a base must be a parameter, so six regions cannot arrive as six
 * bases through a four-argument ABI.  Offsets are what the plan carries. */
#define QWEN_ATT_QG      0U
#define QWEN_ATT_OUT     (QWEN_ATT_QG    + QWEN_ATT_HEADS * HEAD_DIM * 2U * 4U)
#define QWEN_ATT_QUERY   (QWEN_ATT_OUT   + QWEN_ATT_HEADS * HEAD_DIM * 4U)
#define QWEN_ATT_KEY     (QWEN_ATT_QUERY + QWEN_ATT_HEADS * HEAD_DIM * 4U)
#define QWEN_ATT_VALUE   (QWEN_ATT_KEY   + QWEN_ATT_PRIORS * FULL_KV_WIDTH * 4U)
#define QWEN_ATT_SCRATCH (QWEN_ATT_VALUE + QWEN_ATT_PRIORS * FULL_KV_WIDTH * 4U)
#define QWEN_ATT_ARENA   (QWEN_ATT_SCRATCH + 128U)

#define QWEN_REC_STATE  0U
#define QWEN_REC_KEY    (QWEN_REC_STATE + QWEN_REC_DIM * QWEN_REC_DIM * 4U)
#define QWEN_REC_QUERY  (QWEN_REC_KEY   + QWEN_REC_DIM * 4U)
#define QWEN_REC_VALUE  (QWEN_REC_QUERY + QWEN_REC_DIM * 4U)
#define QWEN_REC_CORR   (QWEN_REC_VALUE + QWEN_REC_DIM * 4U)
#define QWEN_REC_OUT    (QWEN_REC_CORR  + QWEN_REC_DIM * 4U)
#define QWEN_REC_ARENA  (QWEN_REC_OUT   + QWEN_REC_DIM * 4U)

static int qwen_parity_same(const float *a, const float *b, uint32_t count) {
  for (uint32_t index = 0; index < count; index++)
    if (qwen_parity_bits(a[index]) != qwen_parity_bits(b[index])) return 0;
  return 1;
}

#if AIUEOS_QWEN35_KOTOBA_PARITY == 3
static uint8_t __attribute__((section(".high_bss"), aligned(16)))
  qwen_att_arena[QWEN_ATT_ARENA];
static uint8_t __attribute__((section(".high_bss"), aligned(8))) qwen_att_plan[96];
static float __attribute__((section(".high_bss")))
  qwen_att_reference[QWEN_ATT_HEADS * HEAD_DIM * 2U];
static float __attribute__((section(".high_bss")))
  qwen_att_weights[AIUEOS_QWEN35_GENERATION_TOKENS];

static float *qwen_att_at(uint32_t offset) {
  return (float *)(void *)(qwen_att_arena + offset);
}

static void qwen_att_fill(uint32_t offset, uint32_t count) {
  float *p = qwen_att_at(offset);
  for (uint32_t index = 0; index < count; index++) p[index] = qwen_parity_value();
}

/* Queries and keys are filled through this instead, and the halving is not
 * cosmetic. `qwen_parity_value` spreads magnitudes over 2^-7..2^15, so a
 * 256-term dot product is around 1e9 and a score around 1e8 -- every
 * difference is then far below `local_exp`'s -87 clamp, every weight but the
 * largest underflows to zero, and the softmax DEGENERATES to picking one
 * prior with weight one. Measured 2026-09-03: with the wide fill, changing
 * `shifted`'s upper clamp from 0.0f to 1.0f left the comparison GREEN,
 * because `w_max / denominator` is one either way.
 *
 * In the model the query and the key have both been through
 * `rms_norm_heads_weighted`, so `q.k/16` is O(1..10) and every prior
 * contributes. Sixteen halvings put the synthetic inputs in that range. The
 * scale is an exact power of two, so no value is rounded on the way in. */
static void qwen_att_fill_narrow(uint32_t offset, uint32_t count) {
  float *p = qwen_att_at(offset);
  for (uint32_t index = 0; index < count; index++) {
    float value = qwen_parity_value();
    for (uint32_t step = 0; step < 16U; step++) value *= 0.5f;
    p[index] = value;
  }
}

static void qwen_att_plan_clear(void) {
  for (uint32_t index = 0; index < 96U; index++) qwen_att_plan[index] = 0;
}
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 4
static uint8_t __attribute__((section(".high_bss"), aligned(16)))
  qwen_rec_arena[QWEN_REC_ARENA];
static uint8_t __attribute__((section(".high_bss"), aligned(8))) qwen_rec_plan[96];
static float __attribute__((section(".high_bss")))
  qwen_rec_state[QWEN_REC_DIM * QWEN_REC_DIM];
static float __attribute__((section(".high_bss"))) qwen_rec_corr[QWEN_REC_DIM];
static float __attribute__((section(".high_bss"))) qwen_rec_out[QWEN_REC_DIM];
#endif

#if AIUEOS_QWEN35_KOTOBA_PARITY == 3

/* Stage 5.  Three modes and a refusal.  The reference half is
 * `attention_deinterleave_c` / `attention_softmax_heads_c` /
 * `attention_zero_position_c` -- what `full_attention` ran before the
 * cutover -- and the object half is the live wrappers `full_attention` calls
 * now, so the plan layout and the address rebase checked are the forward
 * pass's own. */
static int qwen_parity_attention(void) {
  uint32_t index;

  /* mode 0: the query/gate de-interleave. */
  qwen_parity_state = 0x0abcdef1u;
  qwen_att_fill(QWEN_ATT_QG, QWEN_ATT_HEADS * HEAD_DIM * 2U);
  attention_deinterleave_c(qwen_att_reference, qwen_att_at(QWEN_ATT_QG),
                           QWEN_ATT_HEADS);
  for (index = 0; index < QWEN_ATT_HEADS * HEAD_DIM; index++)
    qwen_att_at(QWEN_ATT_OUT)[index] = 0.0f;
  if (!attention_deinterleave(qwen_att_at(QWEN_ATT_OUT),
                              qwen_att_at(QWEN_ATT_QG), QWEN_ATT_HEADS))
    return 0;
  if (!qwen_parity_same(qwen_att_reference, qwen_att_at(QWEN_ATT_OUT),
                     QWEN_ATT_HEADS * HEAD_DIM))
    return 0;

  /* mode 1: the fused softmax over the causal prefix of the KV cache. The
     live wrapper is handed ADDRESSES, as `full_attention` hands it the
     workspace and the decode context, and rebases them itself; every call
     here therefore checks that rebase as well as the arithmetic. */
  qwen_parity_state = 0x13572468u;
  qwen_att_fill(QWEN_ATT_QG, QWEN_ATT_HEADS * HEAD_DIM * 2U);
  qwen_att_fill_narrow(QWEN_ATT_QUERY, QWEN_ATT_HEADS * HEAD_DIM);
  qwen_att_fill_narrow(QWEN_ATT_KEY, QWEN_ATT_PRIORS * FULL_KV_WIDTH);
  qwen_att_fill(QWEN_ATT_VALUE, QWEN_ATT_PRIORS * FULL_KV_WIDTH);
  for (index = 0; index < QWEN_ATT_HEADS * HEAD_DIM * 2U; index++)
    qwen_att_reference[index] = qwen_att_at(QWEN_ATT_QG)[index];
  if (attention_softmax_heads_c(qwen_att_reference,
                                qwen_att_at(QWEN_ATT_QUERY),
                                qwen_att_at(QWEN_ATT_KEY),
                                qwen_att_at(QWEN_ATT_VALUE), qwen_att_weights,
                                QWEN_ATT_HEADS, QWEN_ATT_GROUP,
                                QWEN_ATT_POSITION) !=
      AIUEOS_QWEN35_FAILURE_NONE)
    return 0;
  if (attention_softmax_heads(qwen_att_at(QWEN_ATT_QG),
                              qwen_att_at(QWEN_ATT_QUERY),
                              qwen_att_at(QWEN_ATT_KEY),
                              qwen_att_at(QWEN_ATT_VALUE),
                              qwen_att_at(QWEN_ATT_SCRATCH), QWEN_ATT_HEADS,
                              QWEN_ATT_GROUP, QWEN_ATT_POSITION) !=
      AIUEOS_QWEN35_FAILURE_NONE)
    return 0;
  if (!qwen_parity_same(qwen_att_reference, qwen_att_at(QWEN_ATT_QG),
                     QWEN_ATT_HEADS * HEAD_DIM))
    return 0;

  /* mode 2: the position-zero reduction. */
  qwen_parity_state = 0x2468ace0u;
  qwen_att_fill(QWEN_ATT_QG, QWEN_ATT_HEADS * HEAD_DIM * 2U);
  qwen_att_fill(QWEN_ATT_VALUE, QWEN_ATT_KV_HEADS * HEAD_DIM);
  attention_zero_position_c(qwen_att_reference, qwen_att_at(QWEN_ATT_QG),
                            qwen_att_at(QWEN_ATT_VALUE), QWEN_ATT_HEADS,
                            QWEN_ATT_GROUP);
  for (index = 0; index < QWEN_ATT_HEADS * HEAD_DIM; index++)
    qwen_att_at(QWEN_ATT_OUT)[index] = 0.0f;
  if (!attention_zero_position(qwen_att_at(QWEN_ATT_OUT),
                               qwen_att_at(QWEN_ATT_QG),
                               qwen_att_at(QWEN_ATT_VALUE), QWEN_ATT_HEADS,
                               QWEN_ATT_GROUP))
    return 0;
  if (!qwen_parity_same(qwen_att_reference, qwen_att_at(QWEN_ATT_OUT),
                     QWEN_ATT_HEADS * HEAD_DIM))
    return 0;

  /* A refusal, so a run that never saw the object say no is not a pass.
     Straight to the object: the live wrappers never build mode 3. */
  qwen_att_plan_clear();
  qwen_parity_write_u32(qwen_att_plan, 0, 3);
  if (kotoba_aiueos_qwen35_attention(qwen_att_arena, QWEN_ATT_ARENA,
                                     qwen_att_plan, 96) !=
      (uint64_t)(int64_t)-5)
    return 0;
  return 1;
}

#endif /* == 3 */

#if AIUEOS_QWEN35_KOTOBA_PARITY == 4
/* Stage 6.  The reference half is `recurrent_step_c` -- what
 * `linear_attention` ran before the cutover -- and the object half is the
 * live wrapper `linear_attention` calls now, handed ADDRESSES as the forward
 * pass hands it `decode->recurrent` and the workspace, so the plan layout
 * and the rebase checked are the forward pass's own. */
static int qwen_parity_recurrent(void) {
  float *state = (float *)(void *)(qwen_rec_arena + QWEN_REC_STATE);
  float *key = (float *)(void *)(qwen_rec_arena + QWEN_REC_KEY);
  float *query = (float *)(void *)(qwen_rec_arena + QWEN_REC_QUERY);
  float *value = (float *)(void *)(qwen_rec_arena + QWEN_REC_VALUE);
  float *out = (float *)(void *)(qwen_rec_arena + QWEN_REC_OUT);
  /* 0.9375 and 0.375 are exact in binary32 and inside the ranges
     `linear_attention` produces: `decay = local_exp(transition)` with a
     negative transition, and `beta = sigmoid(beta_values[head])`. */
  float decay = 0.9375f;
  float beta = 0.375f;
  uint32_t index;

  qwen_parity_state = 0x0fedcba9u;
  for (index = 0; index < QWEN_REC_DIM * QWEN_REC_DIM; index++)
    state[index] = qwen_parity_value();
  for (index = 0; index < QWEN_REC_DIM; index++) key[index] = qwen_parity_value();
  for (index = 0; index < QWEN_REC_DIM; index++) query[index] = qwen_parity_value();
  for (index = 0; index < QWEN_REC_DIM; index++) value[index] = qwen_parity_value();
  for (index = 0; index < QWEN_REC_DIM * QWEN_REC_DIM; index++)
    qwen_rec_state[index] = state[index];
  recurrent_step_c(qwen_rec_state, key, query, value, decay, beta,
                   qwen_rec_corr, qwen_rec_out);

  if (!recurrent_step(state, key, query, value, decay, beta,
                      (float *)(void *)(qwen_rec_arena + QWEN_REC_CORR), out))
    return 0;
  /* BOTH halves of the answer: the 65,536-byte state the next token reads and
     the activation this token emits.  A port that got the rank-one update
     wrong but the read-out right passes the second check alone. */
  if (!qwen_parity_same(qwen_rec_state, state, QWEN_REC_DIM * QWEN_REC_DIM))
    return 0;
  if (!qwen_parity_same(qwen_rec_out, out, QWEN_REC_DIM)) return 0;

  /* A refusal: the dimension ceiling is 128 and this asks for 129.
     Straight to the object: the live wrapper always passes 128. */
  for (index = 0; index < 96U; index++) qwen_rec_plan[index] = 0;
  qwen_parity_write_u64(qwen_rec_plan, 8, 129);
  if (kotoba_aiueos_qwen35_recurrent_step(qwen_rec_arena, QWEN_REC_ARENA,
                                          qwen_rec_plan, 96) !=
      (uint64_t)(int64_t)-5)
    return 0;
  return 1;
}

#endif /* == 4 */

#if AIUEOS_QWEN35_KOTOBA_PARITY == 5
/* Stage 7, the rope stage, and the one stage whose reference is NOT the C.
 * `rope_heads_c` takes its sine from x87 `fsincos` and its frequencies from
 * `local_exp`; the object follows Prism llama.cpp 9a9394a instead (iterated
 * theta_scale 0x3f1ab32b, the language's bounded binary64 sine/cosine on the
 * widened angle, binary32 unfused rotation).  So the bit-equality checked here
 * is against `tests/prism_rope_oracle.c`'s reference, transcribed below --
 * the same C that cut the contract's vectors -- and the C's distance from the
 * object is MEASURED and printed (`aiueos_qwen35_rope_distance`), not
 * asserted.  The object half is the live wrapper `full_attention` calls. */
#define QWEN_ROPE_HEADS 24U
#define QWEN_ROPE_FLOATS (QWEN_ROPE_HEADS * HEAD_DIM)

/* 72 KiB together, so outside the low region like the recurrent buffers. */
static float __attribute__((section(".high_bss"))) qwen_rope_object[QWEN_ROPE_FLOATS];
static float __attribute__((section(".high_bss"))) qwen_rope_reference[QWEN_ROPE_FLOATS];
static float __attribute__((section(".high_bss"))) qwen_rope_c[QWEN_ROPE_FLOATS];

static double qwen_rope_f64(uint64_t bits) {
  union { uint64_t bits; double value; } representation = {bits};
  return representation.value;
}

static double qwen_rope_sin_qt(double v) {
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

static double qwen_rope_cos_qt(double v) {
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

/* `reduce-bounded-angle` for the non-negative angles that reach it, where
   round-half-away is floor(x + 0.5) and floor is truncation. */
static void qwen_rope_bounded(float theta, float *sine, float *cosine) {
  double v = (double)theta;
  double nearest = (double)(int64_t)(v * 0.6366197723675814 + 0.5);
  double r = (v - nearest * qwen_rope_f64(0x3ff921fb54442d18ULL)) -
             nearest * qwen_rope_f64(0x3c91a62633145c07ULL);
  uint32_t q = (uint32_t)((int64_t)nearest & 3);
  double s = q == 0 ? qwen_rope_sin_qt(r) : q == 1 ? qwen_rope_cos_qt(r)
           : q == 2 ? -qwen_rope_sin_qt(r) : -qwen_rope_cos_qt(r);
  double c = q == 0 ? qwen_rope_cos_qt(r) : q == 1 ? -qwen_rope_sin_qt(r)
           : q == 2 ? -qwen_rope_cos_qt(r) : qwen_rope_sin_qt(r);
  *sine = (float)s;
  *cosine = (float)c;
}

/* ggml_rope_cache_init + rotate_pairs, NEOX pairs i / i+32 of the first 64. */
static void qwen_rope_prism(float *values, uint32_t heads, uint32_t position) {
  union { uint32_t bits; float value; } scale = {0x3f1ab32bU};
  float theta = (float)position;
  for (uint32_t pair = 0; pair < ROPE_HALF; pair++) {
    float sine, cosine;
    qwen_rope_bounded(theta, &sine, &cosine);
    for (uint32_t head = 0; head < heads; head++) {
      float *vector = values + head * HEAD_DIM;
      float x0 = vector[pair];
      float x1 = vector[pair + ROPE_HALF];
      vector[pair] = x0 * cosine - x1 * sine;
      vector[pair + ROPE_HALF] = x0 * sine + x1 * cosine;
    }
    theta *= scale.value;
  }
}

static void qwen_rope_fill(uint32_t seed, uint32_t count, int expose_pair0) {
  qwen_parity_state = seed;
  for (uint32_t index = 0; index < count; index++) {
    float value = qwen_parity_value();
    qwen_rope_object[index] = value;
    qwen_rope_reference[index] = value;
    qwen_rope_c[index] = value;
  }
  if (expose_pair0) {
    /* x0 = 0, x1 = 1: dimension 0 is exactly -sin(position) and dimension 32
       exactly cos(position), so one ulp in either is a changed bit. */
    qwen_rope_object[0] = qwen_rope_reference[0] = 0.0f;
    qwen_rope_object[ROPE_HALF] = qwen_rope_reference[ROPE_HALF] = 1.0f;
  }
}

static int qwen_rope_case(uint32_t heads, uint32_t position, uint32_t seed,
                          int expose_pair0) {
  qwen_rope_fill(seed, heads * HEAD_DIM, expose_pair0);
  qwen_rope_prism(qwen_rope_reference, heads, position);
  if (!rope_heads(qwen_rope_object, heads, position)) return 0;
  /* The WHOLE heads, so a write past dimension 63 is a mismatch too. */
  return qwen_parity_same(qwen_rope_reference, qwen_rope_object,
                          heads * HEAD_DIM);
}

static int qwen_parity_rope(void) {
  /* The live geometry: 24 query heads and 4 key heads at every position the
     decode reaches (0..7), then the admitted ceiling and the position whose
     pair-0 sine needs the low part of pi/2. */
  for (uint32_t position = 0; position < AIUEOS_QWEN35_GENERATION_TOKENS;
       position++) {
    if (!qwen_rope_case(QWEN_ROPE_HEADS, position, 0x51f15eedu + position, 0))
      return 0;
    if (!qwen_rope_case(4, position, 0x0badcafeu + position, 0)) return 0;
  }
  if (!qwen_rope_case(1, 25735, 0x13579bdfu, 0)) return 0;
  if (!qwen_rope_case(1, 15975, 0x2468ace1u, 1)) return 0;
  /* Refusals, straight to the object: the live wrapper cannot ask for them. */
  if (kotoba_aiueos_qwen35_rope(qwen_rope_object, 1024, 1, 25736) !=
      (uint64_t)(int64_t)-4)
    return 0;
  if (kotoba_aiueos_qwen35_rope(qwen_rope_object, 0, 0, 1) !=
      (uint64_t)(int64_t)-2)
    return 0;
  return 1;
}

static int64_t qwen_rope_ordered(float value) {
  uint32_t bits = qwen_parity_bits(value);
  return (bits & 0x80000000U) ? -(int64_t)(bits & 0x7fffffffU) : (int64_t)bits;
}

/* The distance the cutover introduces, MEASURED: the object and `rope_heads_c`
   over the same 24 query heads at one position.  `differing` counts floats
   whose bits differ (of 6,144; dimensions 64..255 are untouched by both),
   `max_ulp` is the largest distance in binary32 steps.  Returns 0 if the
   object refused. */
int aiueos_qwen35_rope_distance(uint32_t position, uint32_t *differing,
                                uint32_t *max_ulp) {
  uint32_t count = 0, widest = 0;
  qwen_rope_fill(0x7e57d157u + position, QWEN_ROPE_FLOATS, 0);
  rope_heads_c(qwen_rope_c, QWEN_ROPE_HEADS, position);
  if (!rope_heads(qwen_rope_object, QWEN_ROPE_HEADS, position)) return 0;
  for (uint32_t index = 0; index < QWEN_ROPE_FLOATS; index++) {
    int64_t gap = qwen_rope_ordered(qwen_rope_object[index]) -
                  qwen_rope_ordered(qwen_rope_c[index]);
    if (gap < 0) gap = -gap;
    if (gap) count++;
    if ((uint64_t)gap > widest)
      widest = gap > 0xffffffffLL ? 0xffffffffU : (uint32_t)gap;
  }
  *differing = count;
  *max_ulp = widest;
  return 1;
}

#endif /* == 5 */

#endif /* AIUEOS_QWEN35_KOTOBA_PARITY >= 3 */

int aiueos_qwen35_kotoba_parity_selftest(uint32_t stage) {
#if AIUEOS_QWEN35_KOTOBA_PARITY == 1
  if (stage == 0) {
    for (uint32_t index = 0; index < QWEN_PARITY_TYPE_COUNT; index++)
      if (!qwen_parity_dequant(qwen_parity_types[index])) return 0;
    return 1;
  }
  if (stage == 1) return qwen_parity_dot();
  if (stage == 2) {
    for (uint32_t index = 0; index < QWEN_PARITY_TYPE_COUNT; index++)
      if (!qwen_parity_matvec(qwen_parity_types[index])) return 0;
    return 1;
  }
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 2
  if (stage == 3) return qwen_parity_activation();
  if (stage == 4) return qwen_parity_norm();
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 3
  if (stage == 5) return qwen_parity_attention();
#elif AIUEOS_QWEN35_KOTOBA_PARITY == 4
  if (stage == 6) return qwen_parity_recurrent();
#else
  if (stage == 7) return qwen_parity_rope();
#endif
  /* A stage this profile did not compile is a REFUSAL, not a pass: a loop that
     asked for one and got 1 would report `ok` for a comparison that never ran. */
  return 0;
}

#endif
