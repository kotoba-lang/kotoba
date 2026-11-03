/* mutable-object-build built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object: the
   mutable object each writes from a random 32-byte transaction into a random-filled buffer, over object lengths 512 (as
   the kernel passes), 40, 0 .. 600 and past the window, transaction lengths 32, 0 .. 40 and past the window, random
   sequences, and null bases on either side; the answer, the trap outcome and all of both buffers compared. */
#include "diff.h"
#include "build.h"
extern int64_t kotoba_aiueos_mutable_object_build(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_mutable_object_build_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t tx[1024] __attribute__((aligned(16)));
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_mutable_object_build, *n = (void *)kotoba_aiueos_mutable_object_build_native;
  static const int64_t OL[] = {512, 512, 512, 40, 41, 39, 0, 24, 511, 513, -1};
  static const int64_t TL[] = {32, 32, 32, 31, 33, 0, 16, 512, 513, -1};
  for (unsigned k = 0; k < 6000; k++) {
    for (int i = 0; i < 1024; i++) tx[i] = (uint8_t)rnd();
    int64_t ol = k % 5 ? OL[rnd() % 11] : (int64_t)(rnd() % 601), tl = k % 3 ? TL[rnd() % 10] : (int64_t)(rnd() % 41);
    int64_t seq = rnd() % 4 ? (int64_t)(rnd() % 0xffffffffu) : (int64_t)rnd() << 24;
    int64_t t = k % 211 == 1 ? 0 : (int64_t)(uintptr_t)tx;
    built(o, n, 0, k % 199 == 0, 0, ol, seq, t, tl);
  }
  report();
}
