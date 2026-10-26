/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_QWEN35_INFER_H
#define AIUEOS_QWEN35_INFER_H

#include "qwen35_runtime.h"

#include <stdint.h>

#define AIUEOS_QWEN35_BOS_TOKEN 248044U
#define AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN 248046U
#define AIUEOS_QWEN35_WORKSPACE_BYTES 368832U
#define AIUEOS_QWEN35_GENERATION_TOKENS 8U

/* The hybrid decoder owns fixed, volatile state for one bounded sequence:
   - 48 Gated DeltaNet recurrent matrices [48, 48, 128, 128]
   - three retained causal-convolution inputs [48, 10240, 3]
   - eight K/V entries for each of the 16 full-attention layers
   - an integrity shadow for every cached key.
   The model weights remain in the admitted read-only GGUF mapping. */
#define AIUEOS_QWEN35_RECURRENT_BYTES 150994944ULL
#define AIUEOS_QWEN35_CONV_STATE_BYTES 5898240ULL
#define AIUEOS_QWEN35_FULL_CACHE_PLANE_BYTES 524288ULL
#define AIUEOS_QWEN35_FULL_KEY_HASH_BYTES 1024ULL
#define AIUEOS_QWEN35_FULL_KV_BYTES \
  (3ULL * AIUEOS_QWEN35_FULL_CACHE_PLANE_BYTES + \
   AIUEOS_QWEN35_FULL_KEY_HASH_BYTES)
#define AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES \
  ((uint64_t)AIUEOS_QWEN35_WORKSPACE_BYTES + \
   AIUEOS_QWEN35_RECURRENT_BYTES + AIUEOS_QWEN35_CONV_STATE_BYTES + \
   AIUEOS_QWEN35_FULL_KV_BYTES)

enum aiueos_qwen35_failure_stage {
  AIUEOS_QWEN35_FAILURE_NONE = 0,
  AIUEOS_QWEN35_FAILURE_EMBEDDING = 1,
  AIUEOS_QWEN35_FAILURE_ATTENTION_PROJECTION = 2,
  AIUEOS_QWEN35_FAILURE_LINEAR_ALPHA = 3,
  AIUEOS_QWEN35_FAILURE_LINEAR_CONV = 4,
  AIUEOS_QWEN35_FAILURE_LINEAR_DECAY = 5,
  AIUEOS_QWEN35_FAILURE_LINEAR_RECURRENT = 6,
  AIUEOS_QWEN35_FAILURE_LINEAR_OUTPUT = 7,
  AIUEOS_QWEN35_FAILURE_FULL_KEY = 8,
  AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX = 9,
  AIUEOS_QWEN35_FAILURE_FULL_OUTPUT = 10,
  AIUEOS_QWEN35_FAILURE_FFN = 11,
  AIUEOS_QWEN35_FAILURE_STATE_NONFINITE = 12,
  AIUEOS_QWEN35_FAILURE_OUTPUT_NORM = 13,
  AIUEOS_QWEN35_FAILURE_OUTPUT_LOGITS = 14,
  AIUEOS_QWEN35_FAILURE_FULL_QUERY = 15,
  AIUEOS_QWEN35_FAILURE_FULL_CACHE = 16,
  AIUEOS_QWEN35_FAILURE_REFERENCE_TOKEN = 20,
  AIUEOS_QWEN35_FAILURE_OUTPUT_SELECTION = 21
};

struct aiueos_qwen35_first_token_result {
  uint32_t token;
  uint32_t second_token;
  float logit;
  float second_logit;
  uint64_t compute_cycles;
  uint32_t vector_bits;
  uint32_t worker_threads;
};

struct aiueos_qwen35_generation_result {
  uint32_t tokens[AIUEOS_QWEN35_GENERATION_TOKENS];
  uint32_t generated_tokens;
  uint32_t decode_tokens;
  uint32_t vector_bits;
  uint32_t worker_threads;
  uint64_t first_token_cycles;
  uint64_t decode_cycles;
  uint64_t total_cycles;
  /* One-based token/layer coordinates.  failed_layer is zero for failures
     outside the 64-layer trunk (embedding or output head). */
  uint32_t failed_token;
  uint32_t failed_layer;
  uint32_t failure_stage;
};

typedef void (*aiueos_qwen35_progress_fn)(uint32_t completed_layers,
                                          uint32_t total_layers,
                                          int output_head);

void aiueos_qwen35_force_scalar(void);

const char *aiueos_qwen35_failure_stage_label(uint32_t stage);

int aiueos_qwen35_first_token(
    const struct aiueos_qwen35_model *model,
    uint32_t input_token,
    void *workspace,
    uint64_t workspace_bytes,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_first_token_result *result);

/* Greedy BOS-prefill plus bounded autoregressive decode.  first_token_cycles
   covers position zero only; decode_cycles covers positions 1..N-1 only, so
   callers can report real decode tok/s without substituting reciprocal TTFT. */
int aiueos_qwen35_generate(
    const struct aiueos_qwen35_model *model,
    uint32_t input_token,
    uint32_t generated_tokens,
    void *workspace,
    uint64_t workspace_bytes,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_generation_result *result);

#endif
