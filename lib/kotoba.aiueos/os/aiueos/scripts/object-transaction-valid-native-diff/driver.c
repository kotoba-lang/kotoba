/* object-transaction-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid 32-byte transaction records (sector 3 with version 1 or 2, sector 42 or 43 with version 3, payload size 16, the
   FNV-1a of the 16-byte payload at offset 12) with each field then mutated in turn (sector, version, size, checksum,
   payload byte), random records, lengths 0 .. 40 and past the 512-byte window, and a null base; answers and traps
   compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_object_transaction_valid(int64_t, int64_t);
extern int64_t kotoba_aiueos_object_transaction_valid_native(int64_t, int64_t);
static uint8_t buf[1024] __attribute__((aligned(16)));
static void put32(int o, uint32_t v) { for (int i = 0; i < 4; i++) buf[o + i] = (uint8_t)(v >> (8 * i)); }
static uint32_t fnv(const uint8_t *p, int n) { uint64_t h = 2166136261u; for (int i = 0; i < n; i++) h = (h ^ p[i]) * 16777619u; return (uint32_t)h; }
static const uint32_t SEC[] = {3, 42, 43, 0, 1, 2, 4, 41, 44, 0xffffffffu};
static const uint32_t VER[] = {1, 2, 3, 0, 4, 0xffffffffu};
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_object_transaction_valid, *n = (void *)kotoba_aiueos_object_transaction_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 1024; i++) buf[i] = (uint8_t)rnd();
    unsigned s = (unsigned)(rnd() % 3), m = (unsigned)(rnd() % 8);
    uint32_t sector = SEC[s], version = s == 0 ? 1 + (uint32_t)(rnd() % 2) : 3;
    if (m == 1) sector = SEC[rnd() % 10];
    if (m == 2) version = VER[rnd() % 6];
    put32(0, sector); put32(4, version); put32(8, m == 3 ? (uint32_t)(rnd() % 3 ? 15 + rnd() % 3 : rnd()) : 16);
    put32(12, fnv(buf + 16, 16) ^ (m == 4 ? 1u << (rnd() % 32) : 0));
    if (m == 5) buf[16 + rnd() % 16] ^= (uint8_t)(1 + rnd() % 255);
    int64_t len = 32;
    if (m == 6) len = (int64_t)(rnd() % 41);
    if (m == 7 && k % 4 == 0) len = (int64_t)(rnd() % 3 ? 512 + rnd() % 3 : rnd() % 1000);
    if (m == 7 && k % 4 != 0) for (int i = 0; i < 32; i++) buf[i] = (uint8_t)rnd();
    same(o, n, b, len, 0, 0, 0);
  }
  same(o, n, 0, 32, 0, 0, 0); same(o, n, b, -1, 0, 0, 0);
  report();
}
