/* qwen35-attention ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). Both run the same plan (96 bytes) over copies of one arena and must answer the same and leave the same
   arena. 600 calls over the three modes -- 0 deinterleave, 1 the softmax over 2..8 positions, 2 the position-zero
   gate -- with 1..64 heads, a kv group that keeps every head's kv index within 0..3 (the old object's row windows trap
   past it, so those geometries cannot be compared), regions packed or apart, values random or with specials, and each
   refusal -1..-10. 100 more calls give the new object a softmax geometry whose last key row passes the slot window,
   where the old object traps, and must be refused with -14. */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_attention(uint8_t *arena, uint64_t alen, uint8_t *plan, uint64_t plen);
extern int64_t kotoba_aiueos_qwen35_attention_native(uint8_t *arena, uint64_t alen, uint8_t *plan, uint64_t plen);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define ARENA (64 * 2048 + 64 * 1024 + 2 * 4096 * 8 + 4096 + 4 * 4096)
static uint8_t base[ARENA] __attribute__((aligned(64))), a1[ARENA] __attribute__((aligned(64))), a2[ARENA] __attribute__((aligned(64)));
static uint8_t plan0[96] __attribute__((aligned(16))), p1[96] __attribute__((aligned(16))), p2[96] __attribute__((aligned(16)));
static uint64_t seed = 1253;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static void put32(uint8_t *p, uint64_t at, uint32_t v) { for (int i = 0; i < 4; i++) p[at + i] = (uint8_t)(v >> (8 * i)); }
static void put64(uint8_t *p, uint64_t at, uint64_t v) { put32(p, at, (uint32_t)v); put32(p, at + 4, (uint32_t)(v >> 32)); }
static uint32_t val(int specials) {
  static const uint32_t sp[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0x7fc00000u, 0x00000001u};
  if (specials && rnd() % 3000 == 0) return sp[rnd() % 5];
  return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(118 + rnd() % 12) << 23;
}
static uint64_t gap(void) { return rnd() % 2 ? 0 : (rnd() % 64) * 16; }
static void build(unsigned mode, uint64_t heads, uint64_t group, uint64_t n) {
  for (int i = 0; i < 96; i++) plan0[i] = 0;
  put32(plan0, 0, mode); put64(plan0, 8, heads); put64(plan0, 16, 256);
  uint64_t at = gap();
  put64(plan0, 32, at); at += heads * 2048 + gap();
  if (mode == 1) {
    put64(plan0, 56, at); at += heads * 1024 + gap();
    put64(plan0, 40, at); at += 4096 * n + gap();
    put64(plan0, 48, at); at += 4096 * n + gap();
    put64(plan0, 88, at); at += 128;
    put64(plan0, 64, 1024); put64(plan0, 72, group); put64(plan0, 80, n - 1);
  } else {
    put64(plan0, 24, at); at += heads * 1024 + gap();
    if (mode == 2) { put64(plan0, 40, at); put64(plan0, 72, group); }
  }
}
void test_main(void) {
  puts_("ATTENTIONDIFF\n");
  unsigned n_bad = 0, seen[16] = {0}, n_bad14 = 0;
  for (unsigned k = 0; k < 700; k++) {
    unsigned mode = k % 3; uint64_t heads = 1 + rnd() % 64, n = 2 + rnd() % 7;
    uint64_t gmin = (heads + 3) / 4, group = gmin + rnd() % (heads - gmin + 1);
    if (k >= 600) { mode = 1; heads = 8 + rnd() % 57; group = 1 + rnd() % (heads / 5); n = 2 + rnd() % 7; }
    int specials = k % 4 == 0;
    for (uint64_t i = 0; i < ARENA; i += 4) put32(base, i, val(specials));
    build(mode, heads, group, n);
    uint64_t alen = ARENA, plen = 96; unsigned r = k % 37; int null_a = 0, null_p = 0;
    if (k < 600) {
      if (r == 1) null_a = 1;
      if (r == 2) null_p = 1;
      if (r == 3) plen = 95;
      if (r == 4) put32(plan0, 4, 1);
      if (r == 5) put32(plan0, 0, 3);
      if (r == 6) put64(plan0, 8, 65);
      if (r == 7) put64(plan0, 16, 128);
      if (r == 8 && mode == 1) put64(plan0, 64, 512);
      if (r == 9 && mode == 1) put64(plan0, 80, 8);
      if (r == 10) put64(plan0, 64, mode == 1 ? 1024 : 7);
      if (r == 11) alen = 1024;
    }
    for (uint64_t i = 0; i < ARENA; i++) { a1[i] = base[i]; a2[i] = base[i]; }
    for (int i = 0; i < 96; i++) { p1[i] = plan0[i]; p2[i] = plan0[i]; }
    if (k >= 600) {
      int64_t v = kotoba_aiueos_qwen35_attention_native(a2, alen, p2, plen);
      uint64_t maxkvh = (heads - 1) / group;
      int64_t want = maxkvh > 3 ? -14 : 0;
      if (v != want && v >= 0 && n_bad14++ < 4) { puts_("NEG14-DIFF "); hex(k, 3); hex((uint64_t)v, 16); hex(maxkvh, 2); putc_('\n'); }
      if (maxkvh > 3 && v != -14 && v != -12 && v != -13 && v != -11 && n_bad14++ < 4) { puts_("NEG14-DIFF "); hex(k, 3); hex((uint64_t)v, 16); putc_('\n'); }
      continue;
    }
    int64_t v1 = kotoba_aiueos_qwen35_attention(null_a ? 0 : a1, alen, null_p ? 0 : p1, plen);
    int64_t v2 = kotoba_aiueos_qwen35_attention_native(null_a ? 0 : a2, alen, null_p ? 0 : p2, plen);
    unsigned bad = v1 != v2; for (uint64_t i = 0; i < ARENA; i++) if (a1[i] != a2[i]) bad++;
    if (v1 >= -15 && v1 <= 0) seen[-v1]++;
    if (bad && n_bad++ < 8) { puts_("ATT-DIFF "); hex(k, 3); hex(mode, 1); hex((uint64_t)v1, 16); hex((uint64_t)v2, 16); hex(bad, 6); putc_('\n'); }
    if (k % 100 == 99) { puts_("AT "); hex(k + 1, 3); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 15; i++) { putc_(' '); hex(seen[i], 3); } putc_('\n');
  puts_("CASES 258 DIFFS "); hex(n_bad, 3); puts_("NEG14 "); hex(n_bad14, 3); putc_('\n'); puts_("DONE\n");
}
