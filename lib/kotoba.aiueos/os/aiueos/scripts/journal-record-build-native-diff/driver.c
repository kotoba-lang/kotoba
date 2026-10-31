/* journal-record-build built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object: the
   journal record each writes into a random-filled buffer, over lengths 0 .. 600 (the record needs 64 bytes; both trap
   below that, part-way through the writes, and past the 512-byte window) and sequences 0 .. 1200, negative and huge
   (the payload spells the sequence in three decimal digits), and a null base; the answer, the trap outcome and all of
   both buffers compared. */
#include "diff.h"
#include "build.h"
extern int64_t kotoba_aiueos_journal_record_build(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_journal_record_build_native(int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  void *o = (void *)kotoba_aiueos_journal_record_build, *n = (void *)kotoba_aiueos_journal_record_build_native;
  static const int64_t L[] = {512, 512, 512, 64, 65, 63, 0, 1, 48, 511, 513, 600, -1};
  for (unsigned k = 0; k < 6000; k++) {
    int64_t len = k % 3 ? L[rnd() % 13] : (int64_t)(rnd() % 601);
    int64_t seq = k < 1201 ? (int64_t)k : rnd() % 4 ? (int64_t)(rnd() % 1200) : (rnd() % 2 ? -(int64_t)(rnd() % 1000) : (int64_t)rnd() << 20);
    built(o, n, 0, k % 199 == 0, 0, len, seq, 0, 0);
  }
  report();
}
