/* app-lookup-plan built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. The
   native export takes the metadata length right after the metadata (requested, metadata, metadata-length, count,
   stride) where the old one took it last; each case calls both with the same values in their own order. Tables of 1 .. 4
   packed 21-byte records (id[16], length u32, ready u8) whose ids repeat the requested id or differ from it in one byte,
   whose lengths sit around 0, 98304 and random, and whose ready byte is 0, 1 or random; the shipped geometry or one of
   count, stride and metadata length disturbed; null requested or metadata pointers; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_app_lookup_plan(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_app_lookup_plan_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t req[32] __attribute__((aligned(16))), meta[128] __attribute__((aligned(16)));
static void put32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 32; i++) req[i] = (uint8_t)rnd();
    for (int i = 0; i < 128; i++) meta[i] = (uint8_t)rnd();
    int64_t count = 1 + (int64_t)(rnd() % 4);
    for (int a = 0; a < 4; a++) {
      uint8_t *r = meta + 21 * a; unsigned m = (unsigned)(rnd() % 4);
      if (m) for (int i = 0; i < 16; i++) r[i] = req[i];
      if (m == 2) r[rnd() % 16] ^= (uint8_t)(1 + rnd() % 255);
      unsigned l = (unsigned)(rnd() % 6);
      put32(r + 16, l == 0 ? 0 : l == 1 ? 98304 : l == 2 ? 98305 : l == 3 ? 1 + (uint32_t)(rnd() % 98304) : (uint32_t)rnd());
      r[20] = rnd() % 4 ? (uint8_t)(rnd() % 2) : (uint8_t)rnd();
    }
    int64_t stride = 21, mlen = count * 21;
    unsigned d = (unsigned)(rnd() % 8);
    if (d == 1) count = (int64_t)(rnd() % 7) - 1;
    if (d == 2) stride = 20 + (int64_t)(rnd() % 3);
    if (d == 3) mlen = (int64_t)(rnd() % 100);
    if (d == 4) { count = (int64_t)rnd(); mlen = count * 21; }
    int64_t pr = k % 97 == 0 ? 0 : (int64_t)(uintptr_t)req, pm = k % 89 == 0 ? 0 : (int64_t)(uintptr_t)meta;
    int64_t r1 = guarded_call((void *)kotoba_aiueos_app_lookup_plan, pr, pm, count, stride, mlen); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call((void *)kotoba_aiueos_app_lookup_plan_native, pr, pm, mlen, count, stride); int t2 = (int)guard_trapped;
    n_all++; if (t1) n_trap++; else if (r1) n_nz++;
    if ((r1 != r2 || t1 != t2) && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)count, 16); hex((uint64_t)stride, 8); hex((uint64_t)mlen, 16); hex((uint64_t)r1, 16); hex((uint64_t)t1, 1); hex((uint64_t)r2, 16); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  report();
}
