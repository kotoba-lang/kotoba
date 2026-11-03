/* user-object-journal-build built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object:
   the user-object journal record each writes into a random-filled buffer, over lengths 512 (the one it admits), 0, 511,
   513 and random ones, sequences 0 .. 1000 and negative, domains 4 and 5 and refusals, values 0, negative, small and
   random, and a null base; the answer, the trap outcome and all of both buffers compared. */
#include "diff.h"
#include "build.h"
extern int64_t kotoba_aiueos_user_object_journal_build(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_user_object_journal_build_native(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_user_object_journal_build, *n = (void *)kotoba_aiueos_user_object_journal_build_native;
  static const int64_t L[] = {512, 512, 512, 0, 511, 513, 64, -1};
  static const int64_t D[] = {4, 5, 4, 5, 3, 6, 0, -1};
  for (unsigned k = 0; k < 6000; k++) {
    int64_t len = k % 5 ? L[rnd() % 8] : (int64_t)(rnd() % 1000);
    int64_t seq = rnd() % 5 ? (int64_t)(rnd() % 1001) : (int64_t)(rnd() % 3) - 1;
    int64_t dom = D[rnd() % 8];
    int64_t val = rnd() % 4 ? (int64_t)(rnd() % 0xffffffffu) : (int64_t)(rnd() % 3) - 1;
    if (rnd() % 8 == 0) val = (int64_t)rnd() << 24;
    built(o, n, 0, k % 199 == 0, 0, len, seq, dom, val);
  }
  report();
}
