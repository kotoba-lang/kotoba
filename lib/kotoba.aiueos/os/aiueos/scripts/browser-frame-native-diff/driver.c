/* browser-frame built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object (same ABI).
   Random 128-byte window states: ABI word 1 or another, 0..5 windows (ids distinct or repeated, focus naming one of them
   or none), geometry inside the viewport, at its edge, past it, or with a width below 1 or a height below 29; state
   lengths 128 or another; output lengths at, above or below 24 * (1 + 2n); a null state or output. Both objects start
   from the same random output bytes; answers, traps (through the #UD guard) and every output and state byte are
   compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_browser_frame(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_browser_frame_native(int64_t, int64_t, int64_t, int64_t);
static uint32_t st[64], s0[64], o1[96], o2[96];
static unsigned n_frames;
void test_main(void) {
  guard_init(); puts_("FRAMEDIFF\n");
  void *fo = (void *)kotoba_aiueos_browser_frame, *fn = (void *)kotoba_aiueos_browser_frame_native;
  for (unsigned c = 0; c < 20000; c++) {
    for (int i = 0; i < 64; i++) s0[i] = (uint32_t)rnd();
    uint32_t n = rnd() % 10 ? 1 + (uint32_t)(rnd() % 4) : (uint32_t)(rnd() % 6);
    uint32_t vw = rnd() % 10 ? 1920 : (uint32_t)(rnd() % 4000), vh = rnd() % 10 ? 1080 : (uint32_t)(rnd() % 3000);
    s0[0] = rnd() % 20 ? 1 : (uint32_t)(rnd() % 3); s0[1] = n; s0[3] = vw; s0[4] = vh;
    for (uint32_t k = 0; k < 5; k++) {
      uint32_t *w = &s0[5 + 5 * k];
      w[0] = rnd() % 8 ? 100 + k : (uint32_t)(rnd() % 4) + 100;
      unsigned g = (unsigned)(rnd() % 12);
      w[3] = g == 0 ? 0 : 1 + (uint32_t)(rnd() % (vw ? vw : 1)); w[4] = g == 1 ? (uint32_t)(rnd() % 29) : 29 + (uint32_t)(rnd() % (vh > 29 ? vh - 28 : 1));
      w[1] = vw > w[3] ? (uint32_t)(rnd() % (vw - w[3] + (g == 2 ? 5 : 1))) : 0; w[2] = vh > w[4] ? (uint32_t)(rnd() % (vh - w[4] + (g == 3 ? 5 : 1))) : 0;
      if (g == 4) w[1] = (uint32_t)rnd();
    }
    s0[2] = rnd() % 8 ? s0[5 + 5 * (rnd() % (n ? n : 1))] : (uint32_t)(rnd() % 8) + 100;
    int64_t sb = rnd() % 20 ? 128 : (int64_t)(rnd() % 256);
    int64_t need = 24 * (1 + 2 * (int64_t)n), ob = rnd() % 8 ? need + (int64_t)(rnd() % 2) * 24 : need - 1 - (int64_t)(rnd() % 24);
    int nul = c % 97 == 3 ? 1 + (int)(c % 2) : 0;
    for (int i = 0; i < 64; i++) st[i] = s0[i];
    for (int i = 0; i < 96; i++) o1[i] = o2[i] = (uint32_t)rnd();
    int64_t r1 = guarded_call(fo, nul == 1 ? 0 : (int64_t)(uintptr_t)st, sb, nul == 2 ? 0 : (int64_t)(uintptr_t)o1, ob, 0); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(fn, nul == 1 ? 0 : (int64_t)(uintptr_t)st, sb, nul == 2 ? 0 : (int64_t)(uintptr_t)o2, ob, 0); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 96; i++) if (o1[i] != o2[i]) eq = 0;
    for (int i = 0; i < 64; i++) if (st[i] != s0[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1 > 0) { n_nz++; n_frames++; } else if (r1 != 0) n_nz++;
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex(c, 4); hex((uint64_t)r1, 16); hex((uint64_t)t1, 1); hex((uint64_t)r2, 16); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  puts_("FRAMES "); hex(n_frames, 4); putc_('\n');
  report();
}
