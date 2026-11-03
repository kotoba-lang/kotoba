/* superblock-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. Valid
   512-byte superblocks (the magic words, version 3, size 108, a generation 2 .. 5, an object table at offset 36 .. 512
   with a nonzero length that fits the block and its FNV-1a at 32, and the fields at 36, 40, 76 and 80 in range) with one
   field then mutated in turn -- each word, the generation and the table offset and length at and across their bounds
   (which moves the hashed span), the checksum, a byte inside and just outside the span -- plus random blocks, lengths
   other than 512 and a null base; answers and traps compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_superblock_valid(int64_t, int64_t);
extern int64_t kotoba_aiueos_superblock_valid_native(int64_t, int64_t);
static uint8_t buf[1024] __attribute__((aligned(16)));
static void put32(int o, uint32_t v) { for (int i = 0; i < 4; i++) buf[o + i] = (uint8_t)(v >> (8 * i)); }
static uint32_t fnv(const uint8_t *p, unsigned n) { uint64_t h = 2166136261u; for (unsigned i = 0; i < n; i++) h = (h ^ p[i]) * 16777619u; return (uint32_t)h; }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  void *o = (void *)kotoba_aiueos_superblock_valid, *n = (void *)kotoba_aiueos_superblock_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 1024; i++) buf[i] = (uint8_t)rnd();
    uint32_t off = 36 + (uint32_t)(rnd() % 476), len = 1 + (uint32_t)(rnd() % (512 - off));
    if (rnd() % 8 == 0) { off = 36; len = 476; }
    put32(0, 1163217217u); put32(4, 3232582u); put32(8, 3); put32(12, 108); put32(16, 2 + (uint32_t)(rnd() % 4));
    put32(24, off); put32(28, len); put32(36, 4 + (uint32_t)(rnd() % 100)); put32(40, 80 + (uint32_t)(rnd() % 193));
    put32(76, 5 + (uint32_t)(rnd() % 100)); put32(80, 1);
    unsigned m = (unsigned)(rnd() % 12);
    if (m == 1) { static const int W[] = {0, 4, 8, 12, 36, 76, 80}; int w = W[rnd() % 7]; buf[w + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 2) { static const uint32_t G[] = {0, 1, 6, 7, 0xffffffffu}; put32(16, G[rnd() % 5]); }
    if (m == 3) { static const uint32_t X[] = {79, 273, 0, 0xffffffffu}; put32(40, X[rnd() % 4]); }
    if (m == 4) put32(76, (uint32_t)(rnd() % 5));
    if (m == 5) { static const uint32_t F[] = {35, 34, 0, 512, 513, 511}; off = F[rnd() % 6]; put32(24, off); if (off > 512) off = 36; }
    if (m == 6) { len = rnd() % 3 ? 512 - off + 1 + (uint32_t)(rnd() % 3) : (rnd() % 2 ? 0 : 0xffffffffu); put32(28, len); if ((uint64_t)off + len > 512 || len == 0) len = 0; }
    if (m == 7) { len = 512 - off; put32(28, len); }
    uint32_t h = ((uint64_t)off + len <= 512 && len) ? fnv(buf + off, len) : (uint32_t)rnd();
    put32(32, h);
    if (m == 8) buf[32 + rnd() % 4] ^= (uint8_t)(1 << (rnd() % 8));
    if (m == 9 && len) buf[off + rnd() % len] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 10 && (uint64_t)off + len < 512) buf[off + len] ^= 0x5a;                                   /* just past the span: no effect */
    if (m == 11) for (int i = 0; i < 512; i++) buf[i] = (uint8_t)rnd();
    int64_t L = 512;
    if (k % 13 == 5) { static const int64_t LL[] = {0, 31, 32, 511, 513, 64, -1}; L = LL[rnd() % 7]; }
    same(o, n, k % 199 == 0 ? 0 : b, L, 0, 0, 0);
  }
  report();
}
