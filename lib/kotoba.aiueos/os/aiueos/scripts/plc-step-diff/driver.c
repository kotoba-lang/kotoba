#include <stdint.h>
#define DECL(p) void p##_reset(void); int p##_release(uint64_t, int32_t, int32_t); uint64_t p##_call(uint64_t, uint64_t, uint64_t); \
  void p##_poke(uint64_t, int32_t, int32_t, uint64_t); void p##_snap(uint64_t[16]); void p##_extend_budget(uint64_t);
DECL(old) DECL(new)
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 71;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 11; }
static unsigned n_steps, n_commits, n_faults, n_bad, kinds[8];
static int same_state(unsigned tag) {
  uint64_t a[16], b[16]; old_snap(a); new_snap(b);
  for (int i = 0; i < 16; i++) if (a[i] != b[i]) { if (n_bad < 8) { puts_("PLC-DIFF "); hex(tag, 6); hex(i, 2); hex(a[i], 16); hex(b[i], 16); putc_('\n'); } return 0; }
  return 1;
}
static int call_both(uint64_t cap, uint64_t arg, uint64_t t, unsigned tag) {
  uint64_t v1 = old_call(cap, arg, t), v2 = new_call(cap, arg, t); n_steps++;
  if (v1 != v2 || !same_state(tag)) { n_bad++; return 0; }
  return 1;
}
/* one scan: release (sometimes at the wrong tick), then the well-formed calls -- read both inputs, stage both outputs,
   arm the watchdog, commit -- each perturbed with probability 1/7 (wrong argument, repeated, omitted, late tick) or a
   random call injected */
static void scan(unsigned k) {
  uint64_t a[16], now, next; int r1, r2;
  old_snap(a); next = a[10];
  now = (rnd() % 9 == 0) ? next + (rnd() % 3) - 1 : next;
  int32_t i0 = (int32_t)rnd(), i1 = (int32_t)rnd();
  r1 = old_release(now, i0, i1); r2 = new_release(now, i0, i1); n_steps++;
  if (r1 != r2 || !same_state(k * 100)) { n_bad++; return; }
  uint64_t extended = 0;
  if (r1 && rnd() % 8 == 0) { extended = 1 + rnd() % 30; old_extend_budget(extended); new_extend_budget(extended); }   /* budget past the deadline */
  struct { uint64_t cap, arg; } plan[] = {{16, 0}, {16, 1}, {17, (uint32_t)rnd()}, {17, (1ull << 32) | (uint32_t)rnd()},
                                          {19, 1}, {18, 2}};
  uint64_t t = now;
  for (unsigned c = 0; c < 6; c++) {
    uint64_t cap = plan[c].cap, arg = plan[c].arg;
    unsigned p = (unsigned)(rnd() % 7);
    if (c == 5 && extended && (rnd() & 1)) t = now + 9 + rnd() % extended;    /* after the deadline, within the budget */
    if (p == 0) {
      switch (rnd() % 6) {
        case 0: arg ^= (uint64_t)1 << (rnd() % 40); break;
        case 1: if (!call_both(cap, arg, t, k * 100 + 50 + c)) return; break;   /* repeated */
        case 2: continue;                                                    /* omitted */
        case 3: t += rnd() % 9; break;                                       /* late */
        case 4: cap = 15 + rnd() % 6; break;
        default: if (!call_both(rnd() % 21, rnd(), t, k * 100 + 70 + c)) return; break;
      }
    }
    if (!call_both(cap, arg, t, k * 100 + c + 1)) return;
    old_snap(a); if ((a[15] >> 16) & 1) return;
  }
  old_snap(a); if (!(a[15] & 1) && !((a[15] >> 16) & 1)) n_commits++;
}
void test_main(void) {
  puts_("PLCDIFF\n");
  for (unsigned run = 0; run < 300; run++) {
    old_reset(); new_reset();
    /* a run near the 2^32 and 2^63 tick boundaries every so often, and a safe output that is not zero */
    uint64_t base = run % 5 == 1 ? 0xfffffff0ull : run % 5 == 2 ? 0x7ffffffffffffff0ull : run % 5 == 3 ? 0xffffffffffffffe0ull : 10;
    int32_t safe0 = (int32_t)(run % 3 == 0 ? rnd() : 0);
    old_poke(0, 0, safe0, base); new_poke(0, 0, safe0, base);
    for (unsigned k = 0; k < 20; k++) {
      uint64_t a[16]; old_snap(a);
      if ((a[15] >> 16) & 1) break;                          /* latched: the runtime refuses for good */
      if (a[15] & 1) { uint64_t t = a[11] + rnd() % 6; call_both(18, 2, t, run * 100 + k); }   /* an active scan is closed */
      scan(run * 100 + k);
    }
    if (!same_state(run)) n_bad++;
    { uint64_t a[16]; old_snap(a); if ((a[15] >> 16) & 1) { n_faults++; kinds[(a[15] >> 24) & 7]++; } }
  }
  puts_("STEPS "); hex(n_steps, 6); puts_("COMMITS "); hex(n_commits, 5); puts_("FAULTS "); hex(n_faults, 4); puts_("DIFFS "); hex(n_bad, 5); putc_('\n');
  puts_("KINDS "); for (int i = 0; i < 8; i++) hex(kinds[i], 3); putc_('\n'); puts_("DONE\n");
}
