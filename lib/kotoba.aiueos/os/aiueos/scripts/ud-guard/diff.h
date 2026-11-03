/* Shared by the guarded buffer differentials (JUN-552): debugcon output, a fixed-seed generator, and `same`, which calls
   the kotoba-compiler/1 object and the native object on the same arguments through the #UD guard and counts a
   difference when the answers or the trap outcomes differ. */
#include "guard.h"
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 552;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static unsigned n_all, n_nz, n_bad, n_trap;
static int64_t last_old, last_new;
static int last_trap_old, last_trap_new;
/* returns 1 when both objects agree */
__attribute__((unused)) static int same(void *f_old, void *f_new, int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4) {
  last_old = guarded_call(f_old, a0, a1, a2, a3, a4); last_trap_old = (int)guard_trapped;
  last_new = guarded_call(f_new, a0, a1, a2, a3, a4); last_trap_new = (int)guard_trapped;
  n_all++; if (last_trap_old) n_trap++; else if (last_old != 0) n_nz++;
  if (last_old == last_new && last_trap_old == last_trap_new) return 1;
  if (n_bad++ < 10) {
    puts_("DIFF "); hex((uint64_t)a0, 16); hex((uint64_t)a1, 16); hex((uint64_t)a2, 16); hex((uint64_t)a3, 16); hex((uint64_t)a4, 16);
    hex((uint64_t)last_old, 16); hex((uint64_t)last_trap_old, 1); hex((uint64_t)last_new, 16); hex((uint64_t)last_trap_new, 1); putc_('\n');
  }
  return 0;
}
static void report(void) {
  puts_("CASES "); hex(n_all, 8); puts_("NONZERO "); hex(n_nz, 8); puts_("DIFFS "); hex(n_bad, 4); puts_("TRAPS "); hex(n_trap, 8);
  putc_('\n'); puts_("DONE\n");
}
