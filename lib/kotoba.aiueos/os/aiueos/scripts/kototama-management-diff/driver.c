#include <stdint.h>
#include "prelude.h"
uint32_t old_management_command(const uint8_t *, uint32_t, uint8_t *, uint32_t);
uint32_t new_management_command(const uint8_t *, uint32_t, uint8_t *, uint32_t);
struct prelude_runtime runtime;
int reboot_pxe_requested;
static int restart_result; static unsigned restarts;
int aiueos_kototama_runtime_restart(void) { restarts++; return restart_result; }
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 59;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static unsigned n_cases, n_ok, n_bad;
static uint8_t cmd[64], o1[600], o2[600];
static void one(const uint8_t *c, uint32_t n, uint32_t state, int rr, uint8_t *outp, uint32_t cap, unsigned tag) {
  uint32_t r1, r2; unsigned s1, s2; int f1, f2, same;
  for (int i = 0; i < 600; i++) o1[i] = o2[i] = (uint8_t)(0x40 + (i & 31));
  runtime.status.state = (enum aiueos_kototama_runtime_state)state; restart_result = rr;
  reboot_pxe_requested = 0; restarts = 0;
  r1 = old_management_command(c, n, outp ? o1 : 0, cap); s1 = restarts; f1 = reboot_pxe_requested;
  reboot_pxe_requested = 0; restarts = 0;
  r2 = new_management_command(c, n, outp ? o2 : 0, cap); s2 = restarts; f2 = reboot_pxe_requested;
  same = r1 == r2 && s1 == s2 && f1 == f2;
  for (int i = 0; i < 600; i++) if (o1[i] != o2[i]) same = 0;
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; if (n_bad < 10) { puts_("MG-DIFF "); hex(tag, 4); hex(n, 2); hex(state, 1); hex(cap, 3); hex(r1, 2); hex(r2, 2); putc_('\n'); } }
}
static void set(const char *t, uint32_t *n) { uint32_t i = 0; while (t[i]) { cmd[i] = (uint8_t)t[i]; i++; } *n = i; }
void test_main(void) {
  static const char *cmds[] = {"runtime status", "runtime restart", "system reboot-pxe", "runtime", "runtime statu",
    "runtime statuss", "Runtime status", "runtime  status", "system reboot", "system reboot-pxe\n", "", "help"};
  static const uint32_t caps[] = {0, 1, 7, 16, 17, 22, 23, 26, 27, 28, 29, 31, 43, 44, 45, 46, 47, 48, 63, 64, 65, 512};
  puts_("MGMTDIFF\n");
  for (unsigned c = 0; c < sizeof cmds / sizeof *cmds; c++) {
    uint32_t n; set(cmds[c], &n);
    for (uint32_t st = 0; st < 8; st++)
      for (int rr = 0; rr < 2; rr++)
        for (unsigned k = 0; k < sizeof caps / 4; k++) one(cmd, n, st, rr, (uint8_t *)1, caps[k], c * 1000 + st * 100 + k);
    one(cmd, n, 2, 1, 0, 512, 9000 + c);                     /* a null output */
  }
  /* a null command, a length longer than the buffer it names, and every single-byte change of the three commands */
  one(0, 14, 2, 1, (uint8_t *)1, 512, 9100);
  for (unsigned c = 0; c < 3; c++) {
    uint32_t n; set(cmds[c], &n);
    for (uint32_t at = 0; at < n; at++) {
      uint8_t s = cmd[at]; cmd[at] ^= (uint8_t)(1 + rnd() % 255);
      one(cmd, n, rnd() % 7, (int)(rnd() & 1), (uint8_t *)1, 512, 9200 + c * 100 + at); cmd[at] = s;
    }
    one(cmd, n - 1, 2, 1, (uint8_t *)1, 512, 9500 + c); one(cmd, n + 1, 2, 1, (uint8_t *)1, 512, 9600 + c);
  }
  puts_("CASES "); hex(n_cases, 5); puts_("REPLIED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
