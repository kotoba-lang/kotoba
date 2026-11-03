/* qwen35-matvec ported to amu's native object route (check + row exports, run over the plan by
   kernel/qwen35_matvec_plan.h) against the committed kotoba-compiler/1 whole-tensor object (JUN-633). Both run the
   same plan over copies of one arena and must answer the same and leave the same output bytes: every admitted type
   with random blocks, column counts that take the SIMD dot (multiples of 8 up to 16384), the scalar fold (others and
   past 16384), PTQ1_0's fused row dot (up to 16384 columns) and its materialising path past it, and each refusal
   -1 .. -11. */
#include <stdint.h>
#include "../../kernel/qwen35_matvec_plan.h"
extern uint64_t kotoba_aiueos_qwen35_matvec(uint8_t *arena, uint64_t arena_bytes, const uint8_t *plan, uint64_t plan_bytes);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define ARENA (1u << 20)
static uint8_t a1[ARENA] __attribute__((aligned(64))), a2[ARENA] __attribute__((aligned(64)));
static uint8_t plan[96];
static uint64_t seed = 633;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const struct { uint32_t type, block, bytes; } T[] = {
  {0, 1, 4}, {30, 1, 2}, {143, 128, 28}, {8, 32, 34}, {10, 256, 84}, {11, 256, 110}, {12, 256, 144}, {13, 256, 176},
  {14, 256, 210}, {16, 256, 66}, {17, 256, 74}, {18, 256, 98}, {19, 256, 50}, {21, 256, 110}, {22, 256, 82},
  {23, 256, 136}, {29, 256, 56}};
#define NT (sizeof T / sizeof T[0])
static void put64(uint32_t at, uint64_t v) { for (int i = 0; i < 8; i++) plan[at + i] = (uint8_t)(v >> (8 * i)); }
static unsigned n_all, n_ok, n_bad, seen[16];
void test_main(void) {
  puts_("MATVECDIFF\n");
  for (unsigned k = 0; k < 900; k++) {
    unsigned t = k % NT; uint64_t blk = T[t].block, cols;
    unsigned shape = (k / NT) % 6;
    if (blk == 1) cols = shape == 0 ? 8 * (1 + rnd() % 64) : shape == 1 ? 1 + rnd() % 300 : shape == 2 ? 16384 : shape == 3 ? 16392 : 8 * (1 + rnd() % 8) + 3;
    else cols = blk * (shape == 2 ? (16384 / blk) : shape == 3 ? (17408 / blk) : 1 + rnd() % 4);
    uint64_t rows = 1 + rnd() % 3, rb = cols / blk * T[t].bytes;
    if (cols * 4 > 70000 && rows * rb > 300000) rows = 1;
    uint64_t woff = 64, ioff = (woff + rows * rb + 63) & ~63ull, ooff = ioff + cols * 4 + 64, soff = ooff + rows * 4 + 64;
    uint64_t alen = soff + cols * 4 + 64;
    if (alen > ARENA) { rows = 1; ioff = (woff + rb + 63) & ~63ull; ooff = ioff + cols * 4 + 64; soff = ooff + 64; alen = soff + cols * 4 + 64; }
    for (uint64_t i = 0; i < ARENA; i++) a1[i] = 0x5a;
    for (uint64_t i = 0; i < rows * rb; i++) a1[woff + i] = (uint8_t)rnd();
    for (uint64_t i = 0; i < cols; i++) { uint32_t f = (uint32_t)(rnd() % 4 ? 0x3c000000u + (rnd() % 0x8000000u) : rnd()); for (int b = 0; b < 4; b++) a1[ioff + i * 4 + b] = (uint8_t)(f >> (8 * b)); }
    for (uint64_t i = 0; i < ARENA; i++) a2[i] = a1[i];
    for (int i = 0; i < 96; i++) plan[i] = 0;
    put64(0, T[t].type); put64(8, rows); put64(16, cols); put64(24, woff); put64(32, rows * rb);
    put64(40, ioff); put64(48, ooff); put64(56, soff); put64(64, 0); put64(72, rows);
    uint64_t pl = 96; uint8_t *arena1 = a1, *arena2 = a2; uint64_t al = alen;
    unsigned r = k % 37;
    if (r == 1) put64(4, 1) ;
    if (r == 2) put64(80, 7);
    if (r == 3) put64(0, 9);
    if (r == 4) put64(16, 0);
    if (r == 5) put64(16, 65537);
    if (r == 6) put64(8, 0);
    if (r == 7) put64(32, rows * rb + 1);
    if (r == 8) { put64(64, 2); put64(72, 1); }
    if (r == 9) put64(72, rows + 1);
    if (r == 10) al = ooff + 2;
    if (r == 11) pl = 95;
    if (r == 12) { arena1 = 0; arena2 = 0; }
    if (r == 13 && cols * 4 <= 65536) { put64(8, 1048576); put64(32, 1048576 * rb); put64(72, 1048576); }
    uint64_t v1 = kotoba_aiueos_qwen35_matvec(arena1, al, plan, pl);
    uint64_t v2 = qwen_matvec_kotoba(arena2, al, plan, pl);
    unsigned bad = v1 != v2;
    for (uint64_t i = 0; i < ARENA; i++) if (a1[i] != a2[i]) { bad++; }
    n_all++; if (v1 == 0) n_ok++; if ((int64_t)v1 <= 0 && (int64_t)v1 >= -15) seen[-(int64_t)v1]++;
    if (bad && n_bad++ < 10) { puts_("MV-DIFF "); hex(k, 4); hex(T[t].type, 3); hex(cols, 5); hex(rows, 2); hex(v1, 16); hex(v2, 16); hex(bad, 6); putc_('\n'); }
    if (k % 100 == 99) { puts_("AT "); hex(k + 1, 4); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 13; i++) { putc_(' '); hex(seen[i], 4); } putc_('\n');
  puts_("CASES "); hex(n_all, 4); puts_("RAN "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
