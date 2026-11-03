/* kernel/kototama_runtime.c's management protocol before JUN-554 moved it to kotoba/kototama-management.o: text_is,
   text_put, aiueos_kototama_runtime_state_name and aiueos_kototama_runtime_management_command, verbatim (only renamed
   with OLD), over prelude.h's runtime state and restart stub. */
#define OLD(x) old_##x
#define aiueos_kototama_runtime_state_name OLD(state_name)
#define aiueos_kototama_runtime_management_command OLD(management_command)
#include "prelude.h"
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
