/* mutable-object-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid pairs of a 40-byte mutable object and its 32-byte transaction (the magic words, the object id, the sequence,
   size 16, the payload checksum, the payload equal to the transaction's) with one field then mutated in turn (each
   object word, the sequence argument, each transaction word, the checksum, a payload byte on either side), random
   pairs, wrong and over-window lengths, and null bases; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_mutable_object_valid(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_mutable_object_valid_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static uint8_t ob[1024] __attribute__((aligned(16))), tx[1024] __attribute__((aligned(16)));
static void put32(uint8_t *p, int o, uint32_t v) { for (int i = 0; i < 4; i++) p[o + i] = (uint8_t)(v >> (8 * i)); }
static uint32_t fnv(const uint8_t *p, int n) { uint64_t h = 2166136261u; for (int i = 0; i < n; i++) h = (h ^ p[i]) * 16777619u; return (uint32_t)h; }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t bo = (int64_t)(uintptr_t)ob, bt = (int64_t)(uintptr_t)tx;
  void *o = (void *)kotoba_aiueos_mutable_object_valid, *n = (void *)kotoba_aiueos_mutable_object_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 1024; i++) { ob[i] = (uint8_t)rnd(); tx[i] = (uint8_t)rnd(); }
    uint32_t seq = (uint32_t)rnd();
    put32(tx, 8, 16); put32(tx, 12, fnv(tx + 16, 16));
    put32(ob, 0, 1330989377u); put32(ob, 4, 3230274u);
    for (int i = 4; i < 8; i++) ob[4 + i] = tx[i];
    put32(ob, 12, seq); put32(ob, 16, 16); for (int i = 0; i < 4; i++) ob[20 + i] = tx[12 + i];
    for (int i = 0; i < 16; i++) ob[24 + i] = tx[16 + i];
    int64_t ol = 40, tl = 32, sq = seq;
    unsigned m = (unsigned)(rnd() % 10);
    if (m == 1) ob[rnd() % 24] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 2) sq = rnd() % 2 ? (int64_t)seq + 1 : (int64_t)seq | (1ll << 32);
    if (m == 3) tx[4 + rnd() % 12] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 4) { ob[24 + rnd() % 16] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 5) { tx[16 + rnd() % 16] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 6) { uint8_t d = (uint8_t)(1 + rnd() % 255); unsigned i = (unsigned)(rnd() % 16); ob[24 + i] ^= d; tx[16 + i] ^= d;
                  put32(ob, 20, fnv(ob + 24, 16)); for (int j = 0; j < 4; j++) tx[12 + j] = ob[20 + j]; }   /* consistent, other payload */
    if (m == 7) { put32(ob, 16, 17); put32(tx, 8, 17); }
    if (m == 8) { ol = (int64_t)(rnd() % 3 ? rnd() % 48 : 512 + rnd() % 600); tl = rnd() % 2 ? 32 : (int64_t)(rnd() % 48); }
    if (m == 9) { if (rnd() % 2) bo = 0; else bt = 0; }
    same(o, n, bo, ol, sq, bt, tl);
    bo = (int64_t)(uintptr_t)ob; bt = (int64_t)(uintptr_t)tx;
  }
  report();
}
