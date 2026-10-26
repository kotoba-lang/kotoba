/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_KOTOTAMA_RUNTIME_H
#define AIUEOS_KOTOTAMA_RUNTIME_H

#include "qwen35_infer.h"

#include <stdint.h>

enum aiueos_kototama_runtime_state {
  AIUEOS_KOTOTAMA_RUNTIME_EMPTY = 0,
  AIUEOS_KOTOTAMA_RUNTIME_PREPARING = 1,
  AIUEOS_KOTOTAMA_RUNTIME_READY = 2,
  AIUEOS_KOTOTAMA_RUNTIME_RUNNING = 3,
  AIUEOS_KOTOTAMA_RUNTIME_DEGRADED = 4,
  AIUEOS_KOTOTAMA_RUNTIME_STOPPED = 5
};

struct aiueos_kototama_runtime_status {
  enum aiueos_kototama_runtime_state state;
  uint32_t epoch;
  uint32_t restarts;
  uint32_t invocations;
  uint32_t failures;
  uint32_t failed_token;
  uint32_t failed_layer;
  uint32_t failure_stage;
};

/* One global, capability-gated runtime is intentional in the current K16
   slice: the physical node admits exactly one Qwen bundle and one volatile
   decode workspace.  Keeping ownership here means inference failure can reset
   those bytes without resetting the AIUEOS kernel or its network session. */
uint64_t aiueos_kototama_runtime_required_bytes(void);

int aiueos_kototama_runtime_prepare(
    const uint8_t *model_bytes, uint64_t model_bytes_length,
    void *volatile_memory, uint64_t volatile_memory_bytes);

int aiueos_kototama_runtime_invoke(
    uint32_t input_token, uint32_t generated_tokens,
    aiueos_qwen35_progress_fn progress,
    struct aiueos_qwen35_generation_result *result);

int aiueos_kototama_runtime_restart(void);
void aiueos_kototama_runtime_stop(void);
struct aiueos_kototama_runtime_status aiueos_kototama_runtime_status(void);
int aiueos_management_take_reboot_pxe_request(void);
const char *aiueos_kototama_runtime_state_name(
    enum aiueos_kototama_runtime_state state);

/* The SSH command session is a management API, not a root shell.  Only exact
   commands in this bounded dispatcher are executable. */
uint32_t aiueos_kototama_runtime_management_command(
    const uint8_t *command, uint32_t command_length,
    uint8_t *output, uint32_t output_capacity);

#endif
