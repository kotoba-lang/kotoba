/* rtl8125-ring-build built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. Random
   descriptor memory at a 256-aligned base, a base off by 8..248, or a null base; descriptor length 32 or another; frame
   addresses positive, zero, negative or near 2^63; kind -1..2; capacity 0..2049, the kernel's 2048 or random. Both
   objects start from the same 768 random bytes; answers, traps (through the #UD guard) and every byte are compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_rtl8125_ring_build(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_rtl8125_ring_build_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t m0[768] __attribute__((aligned(256))), m1[768] __attribute__((aligned(256))), m2[768] __attribute__((aligned(256)));
void test_main(void) {
  guard_init(); puts_("RINGBUILDDIFF\n");
  void *o = (void *)kotoba_aiueos_rtl8125_ring_build, *n = (void *)kotoba_aiueos_rtl8125_ring_build_native;
  unsigned built[2] = {0, 0};
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 768; i++) m0[i] = (uint8_t)rnd();
    unsigned b = (unsigned)(rnd() % 10);
    int64_t off = b < 7 ? 256 : b < 9 ? 256 + 8 * (int64_t)(1 + rnd() % 31) : -1;
    int64_t dlen = rnd() % 6 ? 32 : (int64_t)(rnd() % 70) - 2;
    unsigned f = (unsigned)(rnd() % 8);
    int64_t fp = f < 5 ? (int64_t)(0x100000 + (rnd() % 0x10000) * 16) : f == 5 ? 0 : f == 6 ? -(int64_t)rnd() : (int64_t)(0x7fffffffffffff00ull | (rnd() & 0xff));
    int64_t kind = rnd() % 5 ? (int64_t)(rnd() % 2) : (int64_t)(rnd() % 4) - 1;
    unsigned c = (unsigned)(rnd() % 6);
    int64_t cap = c < 3 ? 2048 : c == 3 ? (int64_t)(rnd() % 2051) - 1 : c == 4 ? (int64_t)(rnd() % 4) + 2046 : (int64_t)rnd();
    for (int i = 0; i < 768; i++) m1[i] = m2[i] = m0[i];
    int64_t b1 = off < 0 ? 0 : (int64_t)(uintptr_t)(m1 + off), b2 = off < 0 ? 0 : (int64_t)(uintptr_t)(m2 + off);
    int64_t r1 = guarded_call(o, b1, dlen, fp, kind, cap); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(n, b2, dlen, fp, kind, cap); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 768; i++) if (m1[i] != m2[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1 != 0) n_nz++; else built[kind]++;
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex(k, 4); hex((uint64_t)r1, 2); hex((uint64_t)t1, 1); hex((uint64_t)r2, 2); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  puts_("BUILT-TX "); hex(built[0], 8); puts_("BUILT-RX "); hex(built[1], 8); putc_('\n');
  report();
}
