/* user-context-build built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. The
   native export takes the stack's length right after the stack; the old one took (stack, entry, argument, user-stack) and wrote inside a fixed
   4 KiB window. Each case fills a stack buffer with random bytes, places the stack at offset 0 .. 15 in it, and calls the old object and the native one (length 4096, or 4097 .. 16384) with the same
   entry, argument and user-stack words (random, small, higher-half, the i64 extremes); each call starts from the same
   buffer bytes at the same address (the kernel frame stores its own stack address), and the answers, the trap
   outcomes and every byte of the buffer after each call are compared. A null stack is included. */
#include "diff.h"
extern int64_t kotoba_aiueos_user_context_build(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_user_context_build_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t s1[4096 + 64] __attribute__((aligned(16))), s2[4096 + 64], s3[4096 + 64];
static int64_t word(void) { unsigned k = (unsigned)(rnd() % 5); return k == 0 ? (int64_t)rnd() : k == 1 ? (int64_t)(rnd() % 4096) : k == 2 ? (int64_t)(0xffffffff80000000ull | (rnd() & 0x7fffffff)) : k == 3 ? (rnd() % 2 ? INT64_MAX : INT64_MIN) : (int64_t)(rnd() << 20); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 4096 + 64; i++) s1[i] = s2[i] = (uint8_t)rnd();

    int off = (int)(rnd() % 16), null = k % 101 == 0;
    int64_t p1 = null ? 0 : (int64_t)(uintptr_t)(s1 + off), p2 = p1;
    int64_t e = word(), a = word(), us = word(), L = rnd() % 3 ? 4096 : 4097 + (int64_t)(rnd() % 12288);
    int64_t r1 = guarded_call((void *)kotoba_aiueos_user_context_build, p1, e, a, us, 0); int t1 = (int)guard_trapped;
    for (int i = 0; i < 4096 + 64; i++) { s3[i] = s1[i]; s1[i] = s2[i]; }
    int64_t r2 = guarded_call((void *)kotoba_aiueos_user_context_build_native, p2, L, e, a, us); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 4096 + 64; i++) if (s1[i] != s3[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1) n_nz++;
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)off, 2); hex((uint64_t)L, 8); hex((uint64_t)(r1 - p1), 16); hex((uint64_t)t1, 1); hex((uint64_t)(r2 - p2), 16); hex((uint64_t)t2, 1); putc_('\n'); }
  }
  report();
}
