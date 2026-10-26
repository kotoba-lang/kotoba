/* SPDX-License-Identifier: Apache-2.0 */
#include "kototama_runtime.h"

struct aiueos_kototama_runtime {
  struct aiueos_qwen35_model *model;
  uint8_t *workspace;
  uint64_t workspace_bytes;
  struct aiueos_kototama_runtime_status status;
};

static struct aiueos_kototama_runtime runtime;
static int reboot_pxe_requested;

static void bytes_zero(uint8_t *bytes, uint64_t length) {
  if (!bytes) return;
  for (uint64_t i = 0; i < length; i++) bytes[i] = 0;
}

static int text_is(const uint8_t *bytes, uint32_t length, const char *text) {
  uint32_t at = 0;
  if (!bytes || !text) return 0;
  while (text[at]) {
    if (at >= length || bytes[at] != (uint8_t)text[at]) return 0;
    at++;
  }
  return at == length;
}

static uint32_t text_put(uint8_t *out, uint32_t capacity, const char *text) {
  uint32_t length = 0;
  if (!out || !capacity || !text) return 0;
  while (text[length]) {
    if (length >= capacity) return 0;
    out[length] = (uint8_t)text[length];
    length++;
  }
  return length;
}

uint64_t aiueos_kototama_runtime_required_bytes(void) {
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  uint64_t model_bytes =
    ((uint64_t)sizeof(struct aiueos_qwen35_model) + 4095ULL) & ~4095ULL;
  return model_bytes +
    ((AIUEOS_QWEN35_DECODE_WORKSPACE_BYTES + 4095ULL) & ~4095ULL);
#else
  return 0;
#endif
}

int aiueos_kototama_runtime_prepare(
    const uint8_t *model_bytes, uint64_t model_bytes_length,
    void *volatile_memory, uint64_t volatile_memory_bytes) {
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  uint64_t graph_bytes =
    ((uint64_t)sizeof(struct aiueos_qwen35_model) + 4095ULL) & ~4095ULL;
  uint64_t required = aiueos_kototama_runtime_required_bytes();
  runtime = (struct aiueos_kototama_runtime){0};
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_PREPARING;
  runtime.status.epoch = 1;
  if (!model_bytes || !model_bytes_length || !volatile_memory ||
      volatile_memory_bytes < required) {
    runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_DEGRADED;
    runtime.status.failures = 1;
    return 0;
  }
  runtime.model = (struct aiueos_qwen35_model *)volatile_memory;
  runtime.workspace = (uint8_t *)volatile_memory + graph_bytes;
  runtime.workspace_bytes = volatile_memory_bytes - graph_bytes;
  bytes_zero(runtime.workspace, runtime.workspace_bytes);
  if (!aiueos_qwen35_model_parse(model_bytes, model_bytes_length,
                                  model_bytes_length, runtime.model)) {
    runtime.model = 0;
    runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_DEGRADED;
    runtime.status.failures = 1;
    return 0;
  }
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_READY;
  return 1;
#else
  (void)model_bytes;
  (void)model_bytes_length;
  (void)volatile_memory;
  (void)volatile_memory_bytes;
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_STOPPED;
  return 0;
#endif
}

int aiueos_kototama_runtime_invoke(
    uint32_t input_token, uint32_t generated_tokens,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_generation_result *result) {
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  if (!result || !runtime.model || !runtime.workspace ||
      runtime.status.state != AIUEOS_KOTOTAMA_RUNTIME_READY) return 0;
  *result = (struct aiueos_qwen35_generation_result){0};
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_RUNNING;
  runtime.status.invocations++;
  int ok = aiueos_qwen35_generate(
    runtime.model, input_token, generated_tokens,
    runtime.workspace, runtime.workspace_bytes, progress, result);
  if (!ok) {
    runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_DEGRADED;
    runtime.status.failures++;
    runtime.status.failed_token = result->failed_token;
    runtime.status.failed_layer = result->failed_layer;
    runtime.status.failure_stage = result->failure_stage;
    return 0;
  }
  runtime.status.failed_token = 0;
  runtime.status.failed_layer = 0;
  runtime.status.failure_stage = 0;
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_READY;
  return 1;
#else
  (void)input_token;
  (void)generated_tokens;
  (void)progress;
  (void)result;
  return 0;
#endif
}

int aiueos_kototama_runtime_restart(void) {
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  if (!runtime.model || !runtime.workspace || !runtime.workspace_bytes)
    return 0;
  bytes_zero(runtime.workspace, runtime.workspace_bytes);
  runtime.status.epoch++;
  runtime.status.restarts++;
  runtime.status.failed_token = 0;
  runtime.status.failed_layer = 0;
  runtime.status.failure_stage = 0;
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_READY;
  return 1;
#else
  return 0;
#endif
}

void aiueos_kototama_runtime_stop(void) {
#ifdef AIUEOS_QWEN38_MODEL_HANDOFF
  bytes_zero(runtime.workspace, runtime.workspace_bytes);
#endif
  runtime.status.state = AIUEOS_KOTOTAMA_RUNTIME_STOPPED;
}

struct aiueos_kototama_runtime_status aiueos_kototama_runtime_status(void) {
  return runtime.status;
}

int aiueos_management_take_reboot_pxe_request(void) {
  int requested = reboot_pxe_requested;
  reboot_pxe_requested = 0;
  return requested;
}

const char *aiueos_kototama_runtime_state_name(
    enum aiueos_kototama_runtime_state state) {
  switch (state) {
    case AIUEOS_KOTOTAMA_RUNTIME_EMPTY: return "empty";
    case AIUEOS_KOTOTAMA_RUNTIME_PREPARING: return "preparing";
    case AIUEOS_KOTOTAMA_RUNTIME_READY: return "ready";
    case AIUEOS_KOTOTAMA_RUNTIME_RUNNING: return "running";
    case AIUEOS_KOTOTAMA_RUNTIME_DEGRADED: return "degraded";
    case AIUEOS_KOTOTAMA_RUNTIME_STOPPED: return "stopped";
    default: return "invalid";
  }
}

uint32_t aiueos_kototama_runtime_management_command(
    const uint8_t *command, uint32_t command_length,
    uint8_t *output, uint32_t output_capacity) {
  if (text_is(command, command_length, "runtime status")) {
    const char *state = aiueos_kototama_runtime_state_name(runtime.status.state);
    if (runtime.status.state == AIUEOS_KOTOTAMA_RUNTIME_EMPTY)
      state = "unavailable";
    uint32_t at = text_put(output, output_capacity, "aiueos: runtime ");
    if (!at) return 0;
    uint32_t more = text_put(output + at, output_capacity - at, state);
    if (!more) return 0;
    at += more;
    more = text_put(output + at, output_capacity - at, "\n");
    return more ? at + more : 0;
  }
  if (text_is(command, command_length, "runtime restart")) {
    return text_put(output, output_capacity,
      aiueos_kototama_runtime_restart()
        ? "aiueos: runtime restarted\n"
        : "aiueos: runtime restart refused unavailable\n");
  }
  if (text_is(command, command_length, "system reboot-pxe")) {
    reboot_pxe_requested = 1;
    return text_put(output, output_capacity,
                    "aiueos: reboot-pxe scheduled\n");
  }
  return text_put(output, output_capacity,
                  "aiueos: refused unsupported management command\n");
}
