/* qwen35-hadamard ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). kotoba_aiueos_qwen35_hadamard (the committed object) and kotoba_aiueos_qwen35_hadamard_native (the ported
   source compiled by the native root under a test name) run the same signed, scaled Walsh-Hadamard transform on copies
   of one arena and plan and must answer the same and leave the same arena. 300 calls: forward and inverse, widths
   1024..8192 and 65536 (the limit), the head permutation off (rep 0 / 1) or on (hd * nk * rep = width), values random
   or with specials, and each refusal -1..-10 (null arena or plan, a plan length not 64, a nonzero reserved word, a mode
   past 1, a width outside 1024..65536 or not a multiple of 1024, a permutation that does not cover the width, a region
   past the arena, an output overlapping an input, a sign word other than +-1). */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_hadamard(uint8_t *arena, uint64_t alen, uint8_t *plan, uint64_t plen);
extern int64_t kotoba_aiueos_qwen35_hadamard_native(uint8_t *arena, uint64_t alen, uint8_t *plan, uint64_t plen);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define ARENA (3 * 65536 * 4 + 4096)
static uint8_t base[ARENA] __attribute__((aligned(64))), a1[ARENA] __attribute__((aligned(64))), a2[ARENA] __attribute__((aligned(64)));
static uint8_t plan0[64] __attribute__((aligned(16))), p1[64] __attribute__((aligned(16))), p2[64] __attribute__((aligned(16)));
static uint64_t seed = 1024;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static void put32(uint8_t *p, uint64_t at, uint32_t v) { for (int i = 0; i < 4; i++) p[at + i] = (uint8_t)(v >> (8 * i)); }
static void put64(uint8_t *p, uint64_t at, uint64_t v) { put32(p, at, (uint32_t)v); put32(p, at + 4, (uint32_t)(v >> 32)); }
static uint32_t val(int specials) {
  static const uint32_t sp[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0x7fc00000u, 0x00000001u, 0x7f7fffffu};
  if (specials && rnd() % 200 == 0) return sp[rnd() % 6];
  return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(110 + rnd() % 30) << 23;
}
void test_main(void) {
  puts_("HADAMARDDIFF\n");
  unsigned n_bad = 0, seen[12] = {0};
  for (unsigned k = 0; k < 300; k++) {
    uint64_t width = k % 50 == 0 ? 65536 : 1024 * (1 + rnd() % 8);
    uint64_t wb = width * 4, in = 0, sg = wb, out = 2 * wb;
    if (rnd() % 2) { in = 2 * wb; out = 0; }
    int specials = k % 3 == 0;
    for (uint64_t i = 0; i < 3 * wb; i += 4) put32(base, i, val(specials));
    for (uint64_t i = 0; i < width; i++) put32(base, sg + 4 * i, rnd() % 2 ? 1u : 0xffffffffu);
    for (int i = 0; i < 64; i++) plan0[i] = 0;
    put32(plan0, 0, (uint32_t)(rnd() % 2)); put64(plan0, 8, width);
    put64(plan0, 16, in); put64(plan0, 24, sg); put64(plan0, 32, out);
    if (rnd() % 2) { put64(plan0, 56, rnd() % 2); }
    else { uint64_t hd = 64 * (1 + rnd() % 2), rep = 2, nk = width / (hd * rep); put64(plan0, 40, hd); put64(plan0, 48, nk); put64(plan0, 56, rep); }
    uint64_t alen = 3 * wb, plen = 64; unsigned r = k % 23; int null_a = 0, null_p = 0;
    if (r == 1) null_a = 1;
    if (r == 2) null_p = 1;
    if (r == 3) plen = 63;
    if (r == 4) put32(plan0, 4, 1);
    if (r == 5) put32(plan0, 0, 2);
    if (r == 6) put64(plan0, 8, 1000);
    if (r == 7) put64(plan0, 8, width + 1);
    if (r == 8) put64(plan0, 40, 7);
    if (r == 9) alen = 3 * wb - 4;
    if (r == 10) put64(plan0, 32, in);
    if (r == 11) put32(base, sg + 4 * (rnd() % width), 2);
    for (uint64_t i = 0; i < 3 * wb; i++) { a1[i] = base[i]; a2[i] = base[i]; }
    for (int i = 0; i < 64; i++) { p1[i] = plan0[i]; p2[i] = plan0[i]; }
    int64_t v1 = kotoba_aiueos_qwen35_hadamard(null_a ? 0 : a1, alen, null_p ? 0 : p1, plen);
    int64_t v2 = kotoba_aiueos_qwen35_hadamard_native(null_a ? 0 : a2, alen, null_p ? 0 : p2, plen);
    unsigned bad = v1 != v2; for (uint64_t i = 0; i < 3 * wb; i++) if (a1[i] != a2[i]) bad++;
    if (v1 >= -10 && v1 <= 0) seen[-v1]++; else seen[11]++;
    if (bad && n_bad++ < 8) { puts_("HAD-DIFF "); hex(k, 3); hex((uint64_t)v1, 2); hex((uint64_t)v2, 2); hex(width, 5); hex(bad, 6); putc_('\n'); }
    if (k % 50 == 49) { puts_("AT "); hex(k + 1, 3); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 12; i++) { putc_(' '); hex(seen[i], 3); } putc_('\n');
  puts_("CASES "); hex(300, 3); puts_("DIFFS "); hex(n_bad, 3); putc_('\n'); puts_("DONE\n");
}
