/* ipv4-checksum built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object: the
   internet checksum over random buffers at every length 0 .. 2048 and random lengths, half of them all-0xff or all-zero
   runs (the carry folds), the refusals (-1, 2049, huge) and a null base; answers and traps compared. */
#include "diff.h"
#include "frames.h"
extern int64_t kotoba_aiueos_ipv4_checksum(int64_t, int64_t);
extern int64_t kotoba_aiueos_ipv4_checksum_native(int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)kotoba_aiueos_ipv4_checksum, *n = (void *)kotoba_aiueos_ipv4_checksum_native;
  for (unsigned k = 0; k < 6000; k++) {
    int64_t len = k <= 2048 ? (int64_t)k : (int64_t)(rnd() % 2049);
    fill_random();
    if (k % 4 == 1) for (int i = 0; i < FRAME; i++) frame[i] = 0xff;
    if (k % 4 == 2) for (int i = 0; i < FRAME; i++) frame[i] = 0;
    same(o, n, b, len, 0, 0, 0);
  }
  same(o, n, b, -1, 0, 0, 0); same(o, n, b, 2049, 0, 0, 0); same(o, n, b, INT64_MAX, 0, 0, 0); same(o, n, b, INT64_MIN, 0, 0, 0);
  same(o, n, 0, 20, 0, 0, 0); same(o, n, 0, 0, 0, 0, 0);
  report();
}
