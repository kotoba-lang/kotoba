/* qwen35-recurrent-step ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). kotoba_aiueos_qwen35_recurrent_step (the committed object) and kotoba_aiueos_qwen35_recurrent_step_native
   (the ported source compiled by the native root under a test name) run the same gated delta-rule step on copies of
   one arena and plan and must answer the same and leave the same arena. 600 calls: dims 1..8, 16, 32, 64 and 128 (the
   limit), regions packed or placed at random (overlaps included), values random or with specials, decay and beta
   random, and each refusal -1..-7 (null arena or plan, a plan length not 96, a nonzero reserved word, dim 0 or 129, a
   non-finite decay or beta, a region past the arena). */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_recurrent_step(uint8_t *arena, uint64_t alen, uint8_t *plan, uint64_t plen);
extern int64_t kotoba_aiueos_qwen35_recurrent_step_native(uint8_t *arena, uint64_t alen, uint8_t *plan, uint64_t plen);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define ARENA 90000
static uint8_t base[ARENA] __attribute__((aligned(64))), a1[ARENA] __attribute__((aligned(64))), a2[ARENA] __attribute__((aligned(64)));
static uint8_t plan0[96] __attribute__((aligned(16))), p1[96] __attribute__((aligned(16))), p2[96] __attribute__((aligned(16)));
static uint64_t seed = 870;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static void put32(uint8_t *p, int at, uint32_t v) { for (int i = 0; i < 4; i++) p[at + i] = (uint8_t)(v >> (8 * i)); }
static void put64(uint8_t *p, int at, uint64_t v) { put32(p, at, (uint32_t)v); put32(p, at + 4, (uint32_t)(v >> 32)); }
static uint32_t val(int specials) {
  static const uint32_t sp[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0x7fc00000u, 0x00000001u, 0x7f7fffffu};
  if (specials && rnd() % 50 == 0) return sp[rnd() % 6];
  return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(110 + rnd() % 30) << 23;
}
void test_main(void) {
  puts_("RECURRENTDIFF\n");
  static const uint64_t dims[] = {1, 2, 3, 4, 5, 6, 7, 8, 16, 32, 64, 128};
  unsigned n_bad = 0, seen[9] = {0};
  for (unsigned k = 0; k < 600; k++) {
    uint64_t dim = k % 37 == 0 ? 128 : dims[rnd() % 12];
    int specials = k % 4 == 0;
    for (unsigned i = 0; i < ARENA; i += 4) put32(base, (int)i, val(specials));
    for (int i = 0; i < 96; i++) plan0[i] = 0;
    put64(plan0, 8, dim);
    uint64_t sb = dim * dim * 4, vb = dim * 4, off;
    if (rnd() % 2) { off = rnd() % 64 * 4; for (int s = 16; s <= 56; s += 8) { put64(plan0, s, off); off += s == 16 ? sb : vb; } }
    else for (int s = 16; s <= 56; s += 8) { uint64_t len = s == 16 ? sb : vb; put64(plan0, s, (rnd() % ((ARENA - len) / 4 + 1)) * 4); }
    put32(plan0, 64, val(0)); put32(plan0, 72, val(0));
    uint64_t alen = ARENA; uint8_t *ar = 0, *pl = 0; uint64_t plen = 96;
    unsigned r = k % 31;
    if (r == 1) put32(plan0, 0, 1);
    if (r == 2) put64(plan0, 80, 1);
    if (r == 3) put64(plan0, 8, 0);
    if (r == 4) put64(plan0, 8, 129);
    if (r == 5) put32(plan0, 64, 0x7f800000u);
    if (r == 6) put32(plan0, 72, 0x7fc00000u);
    if (r == 7) alen = 64;
    if (r == 8) plen = 95;
    for (unsigned i = 0; i < ARENA; i++) { a1[i] = base[i]; a2[i] = base[i]; }
    for (int i = 0; i < 96; i++) { p1[i] = plan0[i]; p2[i] = plan0[i]; }
    int64_t v1, v2;
    if (r == 9) { v1 = kotoba_aiueos_qwen35_recurrent_step(0, alen, p1, plen); v2 = kotoba_aiueos_qwen35_recurrent_step_native(0, alen, p2, plen); }
    else if (r == 10) { v1 = kotoba_aiueos_qwen35_recurrent_step(a1, alen, 0, plen); v2 = kotoba_aiueos_qwen35_recurrent_step_native(a2, alen, 0, plen); }
    else { ar = a1; pl = p1; v1 = kotoba_aiueos_qwen35_recurrent_step(ar, alen, pl, plen); v2 = kotoba_aiueos_qwen35_recurrent_step_native(a2, alen, p2, plen); }
    unsigned bad = v1 != v2; for (unsigned i = 0; i < ARENA; i++) if (a1[i] != a2[i]) bad++;
    if (v1 >= -7 && v1 <= 0) seen[-v1]++; else seen[8]++;
    if (bad && n_bad++ < 8) { puts_("REC-DIFF "); hex(k, 3); hex((uint64_t)v1, 2); hex((uint64_t)v2, 2); hex(dim, 3); hex(bad, 5); putc_('\n'); }
    if (k % 100 == 99) { puts_("AT "); hex(k + 1, 3); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 9; i++) { putc_(' '); hex(seen[i], 3); } putc_('\n');
  puts_("CASES "); hex(600, 3); puts_("DIFFS "); hex(n_bad, 3); putc_('\n'); puts_("DONE\n");
}
