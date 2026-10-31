/* qwen35-dequant-row ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). Both dequantize the same row into copies of one destination and must answer the same and leave the same
   bytes. Every type the object admits -- F32 0, Q8_0 8, Q2_K 10, Q3_K 11, Q4_K 12, Q5_K 13, Q6_K 14, IQ2_XXS 16,
   IQ2_XS 17, IQ3_XXS 18, IQ1_S 19, IQ3_S 21, IQ2_S 22, IQ4_XS 23, IQ1_M 29, BF16 30, PTQ1_0 143 -- over random block
   bytes, with counts of one to a few blocks and 65536 elements (the limit), and each refusal -1..-6 (null source or
   destination, a destination length not a positive multiple of four, a count past 65536, a source length not the
   row's, an unsupported type). */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_dequant_row(uint64_t t, uint64_t s, uint64_t sl, uint64_t d, uint64_t dl);
extern int64_t kotoba_aiueos_qwen35_dequant_row_native(uint64_t t, uint64_t s, uint64_t sl, uint64_t d, uint64_t dl);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint8_t src[65536 * 4 + 64] __attribute__((aligned(64)));
static uint32_t d1[65536 + 16], d2[65536 + 16];
static uint64_t seed = 584;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const struct { uint32_t type, block, bytes; } T[] = {
  {0, 1, 4}, {30, 1, 2}, {143, 128, 28}, {8, 32, 34}, {10, 256, 84}, {11, 256, 110}, {12, 256, 144}, {13, 256, 176},
  {14, 256, 210}, {16, 256, 66}, {17, 256, 74}, {18, 256, 98}, {19, 256, 50}, {21, 256, 110}, {22, 256, 82},
  {23, 256, 136}, {29, 256, 56}};
#define NT (sizeof T / sizeof T[0])
void test_main(void) {
  puts_("DEQUANTROWDIFF\n");
  unsigned n_bad = 0, n_ok = 0, seen[8] = {0};
  for (unsigned k = 0; k < 1200; k++) {
    unsigned t = (unsigned)(k % NT);
    uint64_t blocks = k % 60 < NT ? 65536 / T[t].block : 1 + rnd() % 4;
    uint64_t count = blocks * T[t].block, sl = blocks * T[t].bytes, dl = count * 4;
    uint32_t type = T[t].type;
    for (uint64_t i = 0; i < sl + 8; i++) src[i] = (uint8_t)rnd();
    for (uint64_t i = 0; i < count + 16; i++) { d1[i] = 0x5a5a5a5au; d2[i] = 0x5a5a5a5au; }
    unsigned r = k % 41; uint64_t sp = (uint64_t)(uintptr_t)src, dp1 = (uint64_t)(uintptr_t)d1, dp2 = (uint64_t)(uintptr_t)d2;
    if (r == 1) sp = 0;
    if (r == 2) { dp1 = 0; dp2 = 0; }
    if (r == 3) dl = dl - 2;
    if (r == 4) dl = 0;
    if (r == 5 && count * 4 <= 65536 * 4) { dl = 65537 * 4; }
    if (r == 6) sl = sl + 1;
    if (r == 7) type = 9;
    if (r == 8) type = 15 + (uint32_t)(rnd() % 2) * 9;
    int64_t v1 = kotoba_aiueos_qwen35_dequant_row(type, sp, sl, dp1, dl);
    int64_t v2 = kotoba_aiueos_qwen35_dequant_row_native(type, sp, sl, dp2, dl);
    unsigned bad = v1 != v2; for (uint64_t i = 0; i < count + 16; i++) if (d1[i] != d2[i]) bad++;
    if (v1 == 0) n_ok++; if (v1 >= -7 && v1 <= 0) seen[-v1]++;
    if (bad && n_bad++ < 10) { puts_("DQ-DIFF "); hex(k, 4); hex(type, 3); hex(count, 5); hex((uint64_t)v1, 16); hex((uint64_t)v2, 16); hex(bad, 5); putc_('\n'); }
    if (k % 200 == 199) { puts_("AT "); hex(k + 1, 4); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 8; i++) { putc_(' '); hex(seen[i], 4); } putc_('\n');
  puts_("CASES 04b0 WRITTEN "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
