/* kotoba/kototama-management.kotoba on the host, for scripts/smoke-kototama-runtime.sh (a host cc build cannot link the
   x86_64-aiueos-kernel-v1 object): the C it replaced, behind the object's interface (JUN-554). The object itself is
   compared with that C under QEMU by scripts/kototama-management-diff. */
#include <stdint.h>
static int is(const uint8_t *b, uint64_t n, const char *t) {
  uint64_t i = 0;
  if (!b) return 0;
  while (t[i]) { if (i >= n || b[i] != (uint8_t)t[i]) return 0; i++; }
  return i == n;
}
int64_t kotoba_aiueos_kototama_command(const uint8_t *cmd, uint64_t n) {
  if ((n >> 32)) return 0;
  return is(cmd, n, "runtime status") ? 1 : is(cmd, n, "runtime restart") ? 2 : is(cmd, n, "system reboot-pxe") ? 3 : 0;
}
static int64_t put(uint8_t *o, uint64_t cap, int64_t at, const char *t) {
  for (uint64_t i = 0; t[i]; i++) { if (at < 0 || (uint64_t)at + i >= cap) return -1; o[at + i] = (uint8_t)t[i]; }
  return at < 0 ? -1 : at + (int64_t)__builtin_strlen(t);
}
int64_t kotoba_aiueos_kototama_reply(uint64_t kind, uint64_t state, uint8_t *o, uint64_t cap) {
  static const char *names[] = {"unavailable", "preparing", "ready", "running", "degraded", "stopped"};
  int64_t r;
  if (!o || (cap >> 32) || (kind >> 32) || (state >> 32)) return 0;
  switch (kind) {
    case 1: r = put(o, cap, put(o, cap, put(o, cap, 0, "aiueos: runtime "), state < 6 ? names[state] : "invalid"), "\n"); break;
    case 2: r = put(o, cap, 0, "aiueos: runtime restarted\n"); break;
    case 3: r = put(o, cap, 0, "aiueos: runtime restart refused unavailable\n"); break;
    case 4: r = put(o, cap, 0, "aiueos: reboot-pxe scheduled\n"); break;
    case 5: r = put(o, cap, 0, "aiueos: refused unsupported management command\n"); break;
    default: r = -1;
  }
  return r < 0 ? 0 : r;
}
