/* user-object-journal-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid 64-byte user-object journal records come from the kotoba-compiler/1 user-object-journal-build object (linked
   from ../user-object-journal-build-native-diff/old.o) for random sequences, domains 4 and 5 and values; then one input
   is mutated in turn (a header byte or word, the sequence to 0 or 1000 and up, any of the three checksums, a byte
   under each, the domain argument or byte, the value to 0, a trailing byte), plus random records, lengths other than 64
   and a null base; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_user_object_journal_build(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_user_object_journal_valid(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_user_object_journal_valid_native(int64_t, int64_t, int64_t);
static uint8_t buf[1024] __attribute__((aligned(16)));
static void put32(int o, uint32_t v) { for (int i = 0; i < 4; i++) buf[o + i] = (uint8_t)(v >> (8 * i)); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_user_object_journal_valid, *n = (void *)kotoba_aiueos_user_object_journal_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 1024; i++) buf[i] = (uint8_t)rnd();
    int64_t dom = 4 + (int64_t)(rnd() % 2);
    if (!kotoba_aiueos_user_object_journal_build(b, 512, 1 + (int64_t)(rnd() % 999), dom, 1 + (int64_t)(rnd() % 0xfffffffeu))) { puts_("BUILD-FAILED\n"); return; }
    int64_t len = 64, d = dom;
    unsigned m = (unsigned)(rnd() % 12);
    if (m == 1) buf[rnd() % 24] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 2) put32(12, rnd() % 2 ? 0 : 1000 + (uint32_t)(rnd() % 3));
    if (m == 3) buf[24 + rnd() % 8] ^= (uint8_t)(1 << (rnd() % 8));
    if (m == 4) buf[44 + rnd() % 4] ^= (uint8_t)(1 << (rnd() % 8));
    if (m == 5) buf[32 + rnd() % 32] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 6) d = rnd() % 2 ? 9 - dom : (int64_t)(rnd() % 8);
    if (m == 7) { put32(56, 0); }
    if (m == 8) len = (int64_t)(rnd() % 3 ? rnd() % 513 : 63 + rnd() % 3);
    if (m == 9) for (int i = 0; i < 64; i++) buf[i] = (uint8_t)rnd();
    if (m == 10) buf[60 + rnd() % 4] = (uint8_t)(1 + rnd() % 255);
    if (m == 11) buf[rnd() % 28] ^= (uint8_t)(1 + rnd() % 255);
    same(o, n, k % 199 == 0 ? 0 : b, len, d, 0, 0);
  }
  report();
}
