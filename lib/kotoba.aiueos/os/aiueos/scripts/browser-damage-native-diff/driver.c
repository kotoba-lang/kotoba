/* browser-damage built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object (same ABI).
   Random current draw lists of 1..261 ops (rects and glyphs with random or small geometry, an invalid kind now and then)
   and 8192-byte shadows: no previous frame, or a previous list that is the current one with a few slots changed, added
   or removed, or unrelated; the viewport set or zero; counts 0..262, list lengths at, above or below n*24, shadow lengths
   8192 or another, and a null list or shadow. Both objects start from the same list and shadow bytes; answers, traps
   (through the #UD guard), every shadow byte (the answer rectangle, the box scratch and the copied list) and the list
   bytes are compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_browser_damage(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_browser_damage_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint32_t ol[262 * 6 + 16], h0[2048 + 16], h1[2048 + 16], h2[2048 + 16], o1[262 * 6 + 16];
static unsigned n_damage, n_whole, n_clean;
static uint32_t geo(void) { unsigned m = (unsigned)(rnd() % 8); return m < 5 ? (uint32_t)(rnd() % 1920) : m == 5 ? 0 : m == 6 ? (uint32_t)(rnd() % 16) : (uint32_t)rnd(); }
static void op(uint32_t *w) { w[0] = rnd() % 30 ? 1 + (uint32_t)(rnd() % 2) : (uint32_t)(rnd() % 4); for (int k = 1; k < 6; k++) w[k] = geo(); }
void test_main(void) {
  guard_init(); puts_("DAMAGEDIFF\n");
  void *fo = (void *)kotoba_aiueos_browser_damage, *fn = (void *)kotoba_aiueos_browser_damage_native;
  for (unsigned c = 0; c < 6000; c++) {
    for (int i = 0; i < 2048 + 16; i++) h0[i] = (uint32_t)rnd();
    int64_t n = rnd() % 10 ? 1 + (int64_t)(rnd() % 40) : (int64_t)(rnd() % 263);
    if (rnd() % 20 == 0) n = 261;
    for (int j = 0; j < 262; j++) op(&ol[j * 6]);
    unsigned pm = (unsigned)(rnd() % 6);
    uint32_t p = pm == 0 ? 0 : pm < 4 ? (uint32_t)n + (uint32_t)(rnd() % 3) - 1 : (uint32_t)(rnd() % 263);
    if (p > 261 && rnd() % 2) p = 261;
    h0[0] = p; for (int j = 0; j < 262; j++) for (int k = 0; k < 6; k++) h0[8 + j * 6 + k] = ol[j * 6 + k];
    if (pm && pm < 4) { unsigned ch = (unsigned)(rnd() % 4); for (unsigned t = 0; t < ch; t++) op(&h0[8 + (rnd() % 262) * 6]); }
    if (pm >= 4) for (int j = 0; j < 262; j++) op(&h0[8 + j * 6]);
    h0[5] = rnd() % 30 ? 1920 : 0; h0[6] = rnd() % 30 ? 1080 : (uint32_t)(rnd() % 2);
    int64_t ob = rnd() % 8 ? n * 24 + (int64_t)(rnd() % 2) * 24 : n * 24 - 1 - (int64_t)(rnd() % 24);
    int64_t hb = rnd() % 20 ? 8192 : 8188 + 4 * (int64_t)(rnd() % 3);
    int nul = c % 89 == 7 ? 1 + (int)(c % 2) : 0;
    for (int i = 0; i < 2048 + 16; i++) h1[i] = h2[i] = h0[i];
    for (int i = 0; i < 262 * 6 + 16; i++) o1[i] = ol[i];
    int64_t r1 = guarded_call(fo, nul == 1 ? 0 : (int64_t)(uintptr_t)ol, ob, nul == 2 ? 0 : (int64_t)(uintptr_t)h1, hb, n); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(fn, nul == 1 ? 0 : (int64_t)(uintptr_t)ol, ob, nul == 2 ? 0 : (int64_t)(uintptr_t)h2, hb, n); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 2048 + 16; i++) if (h1[i] != h2[i]) eq = 0;
    for (int i = 0; i < 262 * 6 + 16; i++) if (o1[i] != ol[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1 != 0) n_nz++;
    if (!t1 && r1 > 0) { if (p == 0) n_whole++; else n_damage++; } else if (!t1 && r1 == 0) n_clean++;
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex(c, 4); hex((uint64_t)r1, 16); hex((uint64_t)t1, 1); hex((uint64_t)r2, 16); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  puts_("WHOLE "); hex(n_whole, 4); puts_("DAMAGED "); hex(n_damage, 4); puts_("UNCHANGED "); hex(n_clean, 4); putc_('\n');
  report();
}
