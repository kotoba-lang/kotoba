/* digest-equal built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. Pairs of
   32-byte digests (random, equal, equal but for one byte at every position, equal but for one bit, aligned and one byte off), lengths 32 and
   others (0 .. 600, around 32, random), and a null pointer on either side; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_digest_equal(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_digest_equal_native(int64_t, int64_t, int64_t);
static uint8_t a[64] __attribute__((aligned(16))), b[64] __attribute__((aligned(16)));
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_digest_equal, *n = (void *)kotoba_aiueos_digest_equal_native;
  for (unsigned k = 0; k < 40000; k++) {
    for (int i = 0; i < 64; i++) a[i] = b[i] = (uint8_t)rnd();
    unsigned m = (unsigned)(rnd() % 6);
    if (m == 1) b[k % 32] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 2) b[rnd() % 32] ^= (uint8_t)(1 << (rnd() % 8));
    if (m == 3) for (int i = 0; i < 32; i++) b[i] = (uint8_t)rnd();
    if (m == 4) b[32 + rnd() % 32] ^= 1;
    int64_t len = 32; unsigned l = (unsigned)(rnd() % 10);
    if (l == 7) len = 31 + (int64_t)(rnd() % 3);
    if (l == 8) len = (int64_t)(rnd() % 601);
    if (l == 9) len = (int64_t)rnd();
    int64_t pa = (int64_t)(uintptr_t)(a + (k % 3 == 2 ? 1 : 0)), pb = (int64_t)(uintptr_t)(b + (k % 3 == 2 ? 1 : 0));
    if (k % 97 == 0) pa = 0;
    if (k % 89 == 0) pb = 0;
    same(o, n, pa, pb, len, 0, 0);
  }
  report();
}
