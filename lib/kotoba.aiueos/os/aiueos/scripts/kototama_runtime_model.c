#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "../kernel/kototama_runtime.h"

static uint32_t generations;

static int contains(const uint8_t *bytes, uint32_t length,
                    const char *text, uint32_t text_length) {
  if (!bytes || !text || text_length > length) return 0;
  for (uint32_t at = 0; at <= length - text_length; at++)
    if (!memcmp(bytes + at, text, text_length)) return 1;
  return 0;
}

int aiueos_qwen35_model_parse(const uint8_t *bytes, uint64_t length,
                              uint64_t admitted_length,
                              struct aiueos_qwen35_model *model) {
  return bytes && length == 4 && admitted_length == length && model;
}

int aiueos_qwen35_generate(
    const struct aiueos_qwen35_model *model, uint32_t input_token,
    uint32_t generated_tokens, void *workspace, uint64_t workspace_bytes,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_generation_result *result) {
  (void)progress;
  if (!model || input_token != AIUEOS_QWEN35_BOS_TOKEN ||
      generated_tokens != AIUEOS_QWEN35_GENERATION_TOKENS ||
      !workspace || workspace_bytes < AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES ||
      !result) return 0;
  ((uint8_t *)workspace)[workspace_bytes - 1] = 0xa5;
  generations++;
  if (generations == 1) {
    result->failed_token = 2;
    result->failed_layer = 4;
    result->failure_stage = AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX;
    return 0;
  }
  result->generated_tokens = generated_tokens;
  result->decode_tokens = generated_tokens - 1;
  result->tokens[0] = AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN;
  return 1;
}

int main(void) {
  const uint8_t model[4] = {'G', 'G', 'U', 'F'};
  uint64_t bytes = aiueos_kototama_runtime_required_bytes();
  uint8_t *memory = (uint8_t *)malloc((size_t)bytes);
  struct aiueos_qwen35_generation_result result = {0};
  if (!memory || !aiueos_kototama_runtime_prepare(
        model, sizeof(model), memory, bytes)) return 1;
  if (aiueos_kototama_runtime_status().state !=
      AIUEOS_KOTOTAMA_RUNTIME_READY) return 2;
  if (aiueos_kototama_runtime_invoke(
        AIUEOS_QWEN35_BOS_TOKEN, AIUEOS_QWEN35_GENERATION_TOKENS,
        0, &result)) return 3;
  struct aiueos_kototama_runtime_status failed =
    aiueos_kototama_runtime_status();
  if (failed.state != AIUEOS_KOTOTAMA_RUNTIME_DEGRADED ||
      failed.failed_token != 2 || failed.failed_layer != 4 ||
      failed.failure_stage != AIUEOS_QWEN35_FAILURE_FULL_SOFTMAX) return 4;
  if (!aiueos_kototama_runtime_restart()) return 5;
  if (memory[bytes - 1] != 0) return 6;
  result = (struct aiueos_qwen35_generation_result){0};
  if (!aiueos_kototama_runtime_invoke(
        AIUEOS_QWEN35_BOS_TOKEN, AIUEOS_QWEN35_GENERATION_TOKENS,
        0, &result)) return 7;
  if (result.tokens[0] != AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN) return 8;
  uint8_t output[96];
  uint32_t length = aiueos_kototama_runtime_management_command(
    (const uint8_t *)"runtime status", 14, output, sizeof(output));
  if (length != 22 || memcmp(output, "aiueos: runtime ready\n", 22)) return 9;
  length = aiueos_kototama_runtime_management_command(
    (const uint8_t *)"system reboot-pxe", 17, output, sizeof(output));
  if (length != 29 || memcmp(output, "aiueos: reboot-pxe scheduled\n", 29) ||
      !aiueos_management_take_reboot_pxe_request() ||
      aiueos_management_take_reboot_pxe_request()) return 10;
  length = aiueos_kototama_runtime_management_command(
    (const uint8_t *)"uname -a", 8, output, sizeof(output));
  if (!length || !contains(output, length, "refused", 7)) return 11;
  struct aiueos_kototama_runtime_status ready =
    aiueos_kototama_runtime_status();
  if (ready.epoch != 2 || ready.restarts != 1 ||
      ready.invocations != 2 || ready.failures != 1) return 12;
  free(memory);
  return 0;
}
