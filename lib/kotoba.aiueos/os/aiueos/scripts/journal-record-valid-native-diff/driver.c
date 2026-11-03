/* journal-record-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid 64-byte journal records come from the kotoba-compiler/1 journal-record-build object (linked from
   ../journal-record-build-native-diff/old.o) for random sequences; then one field is mutated in turn (each header word,
   the sequence to 0, either checksum, a byte under either checksum), plus random records, lengths other than 64 (0 ..
   600) and a null base; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_journal_record_build(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_journal_record_valid(int64_t, int64_t);
extern int64_t kotoba_aiueos_journal_record_valid_native(int64_t, int64_t);
static uint8_t buf[1024] __attribute__((aligned(16)));
static void put32(int o, uint32_t v) { for (int i = 0; i < 4; i++) buf[o + i] = (uint8_t)(v >> (8 * i)); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_journal_record_valid, *n = (void *)kotoba_aiueos_journal_record_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 1024; i++) buf[i] = (uint8_t)rnd();
    if (!kotoba_aiueos_journal_record_build(b, 512, 1 + (int64_t)(rnd() % 999))) { puts_("BUILD-FAILED\n"); return; }
    int64_t len = 64;
    unsigned m = (unsigned)(rnd() % 9);
    if (m == 1) buf[rnd() % 24] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 2) put32(12, 0);
    if (m == 3) buf[24 + rnd() % 8] ^= (uint8_t)(1 << (rnd() % 8));
    if (m == 4) buf[32 + rnd() % 32] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 5) buf[rnd() % 28] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 6) len = (int64_t)(rnd() % 3 ? rnd() % 601 : 63 + rnd() % 3);
    if (m == 7) for (int i = 0; i < 64; i++) buf[i] = (uint8_t)rnd();
    if (m == 8) { put32(12, (uint32_t)rnd()); }
    same(o, n, k % 199 == 0 ? 0 : b, len, 0, 0, 0);
  }
  report();
}
