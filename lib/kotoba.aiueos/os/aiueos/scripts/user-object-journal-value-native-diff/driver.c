/* user-object-journal-value built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object:
   the u32 at offset 56 of random buffers, every length 0 .. 600 (the reads need 60 bytes; both routes trap below that
   and above the 512-byte window), a null base, and random lengths; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_user_object_journal_value(int64_t, int64_t);
extern int64_t kotoba_aiueos_user_object_journal_value_native(int64_t, int64_t);
static uint8_t buf[1024] __attribute__((aligned(16)));
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_user_object_journal_value, *n = (void *)kotoba_aiueos_user_object_journal_value_native;
  for (unsigned k = 0; k < 3000; k++) {
    int64_t len = k <= 600 ? (int64_t)k : (int64_t)(rnd() % 700);
    for (int i = 0; i < 1024; i++) buf[i] = (uint8_t)rnd();
    if (k % 7 == 0) for (int i = 56; i < 60; i++) buf[i] = 0xff;
    same(o, n, b, len, 0, 0, 0);
  }
  same(o, n, 0, 64, 0, 0, 0); same(o, n, b, -1, 0, 0, 0); same(o, n, b, INT64_MIN, 0, 0, 0);
  report();
}
