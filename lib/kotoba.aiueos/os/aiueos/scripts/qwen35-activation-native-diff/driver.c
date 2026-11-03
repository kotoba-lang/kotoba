/* qwen35-activation ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). The old export is (mode, a, b, count, spare) with spare the conv history's address, over the whole vector
   in every mode; the new is (mode | channel << 8, a, a-length, b, b-length, h, h-length, count), with the conv
   (modes 5, 6) one channel per call. Each call is made to the old object once and to the new as the C makes it
   (conv4 looping the channels, stopping at the first refusal), on copies of the same values and history, and must
   answer the same and leave the same bytes. 3000 calls: modes 0..6, counts 1..300 and 65536 (the limit), values
   random over a wide range or with +-0, +-inf, NaNs and denormals, the conv's history present or (mode 5) absent, and
   each old refusal (-1 null values, -2 a mode past 6, -3 a count outside 1..65536, -4 a null b in modes 4..6, -5 a
   null history in mode 6). 200 more give the new object a length the shape does not give, or a channel past count,
   and must be refused with -9. */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_activation(uint64_t mode, uint64_t a, uint64_t b, uint64_t count, uint64_t spare);
extern int64_t kotoba_aiueos_qwen35_activation_native(uint64_t mc, uint64_t a, uint64_t an, uint64_t b, uint64_t bn,
                                                      uint64_t h, uint64_t hn, uint64_t count);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define MAXN 65536
static uint32_t a0[MAXN], a1[MAXN], a2[MAXN], bb[4 * MAXN], h0[3 * MAXN], h1[3 * MAXN], h2[3 * MAXN];
static uint64_t seed = 691;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static uint32_t val(unsigned kind) {
  static const uint32_t sp[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0x00000001u};
  if (kind == 1 && rnd() % 30 == 0) return sp[rnd() % 6];
  return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(100 + rnd() % 40) << 23;     /* about 2^-27 .. 2^12 */
}
static int64_t new_call(uint64_t mode, uint64_t a, uint64_t an, uint64_t b, uint64_t bn, uint64_t h, uint64_t hn, uint64_t count) {
  if (mode != 5 && mode != 6) return kotoba_aiueos_qwen35_activation_native(mode, a, an, b, bn, h, hn, count);
  uint64_t c = 0; int64_t v;
  do { v = kotoba_aiueos_qwen35_activation_native(mode | c << 8, a, an, b, bn, h, hn, count); if (v) return v; } while (++c < count);
  return 0;
}
void test_main(void) {
  puts_("ACTDIFF\n");
  unsigned n_bad = 0, seen[10] = {0}, n_bad9 = 0;
  for (unsigned k = 0; k < 3200; k++) {
    uint64_t mode = k % 7, count = k % 97 == 0 ? 65536 : 1 + rnd() % 300;
    unsigned kind = (unsigned)(rnd() % 2);
    for (uint64_t i = 0; i < count; i++) { a0[i] = val(kind); a1[i] = a0[i]; a2[i] = a0[i]; }
    for (uint64_t i = 0; i < 4 * count; i++) bb[i] = val(kind);
    for (uint64_t i = 0; i < 3 * count; i++) { h0[i] = val(kind); h1[i] = h0[i]; h2[i] = h0[i]; }
    uint64_t a1p = (uint64_t)(uintptr_t)a1, a2p = (uint64_t)(uintptr_t)a2, bp = (uint64_t)(uintptr_t)bb;
    uint64_t h1p = (uint64_t)(uintptr_t)h1, h2p = (uint64_t)(uintptr_t)h2;
    if (mode == 5 && rnd() % 3 == 0) { h1p = 0; h2p = 0; }
    uint64_t xmode = mode, xc = count;
    uint64_t bn = mode == 4 ? count * 4 : count * 16;
    if (k >= 3000) {
      int64_t v; unsigned r = k % 4;
      if (r == 0) v = kotoba_aiueos_qwen35_activation_native(mode, a2p, count * 4 + 4, bp, bn, h2p, h2p ? count * 12 : 0, count);
      else if (r == 1 && mode >= 4) v = kotoba_aiueos_qwen35_activation_native(mode, a2p, count * 4, bp, bn + 4, h2p, h2p ? count * 12 : 0, count);
      else if (r == 2 && mode >= 5 && h2p) v = kotoba_aiueos_qwen35_activation_native(mode, a2p, count * 4, bp, bn, h2p, count * 12 - 4, count);
      else if (mode >= 5) v = kotoba_aiueos_qwen35_activation_native(mode | count << 8, a2p, count * 4, bp, bn, h2p, h2p ? count * 12 : 0, count);
      else v = kotoba_aiueos_qwen35_activation_native(mode, a2p, count * 4 - 4, bp, bn, 0, 0, count);
      if (v != -9 && n_bad9++ < 4) { puts_("NEG9-DIFF "); hex(k, 4); hex(mode, 1); hex((uint64_t)v, 16); putc_('\n'); }
      continue;
    }
    unsigned r = k % 31;
    if (r == 1) { a1p = 0; a2p = 0; }
    if (r == 2) xmode = 7 + rnd() % 3;
    if (r == 3) xc = 0;
    if (r == 4) xc = 65537;
    if (r == 5 && mode >= 4) bp = 0;
    if (r == 6 && mode == 6) { h1p = 0; h2p = 0; }
    uint64_t an = xc * 4, xbn = xmode == 4 ? xc * 4 : xc * 16, hn = h2p ? xc * 12 : 0;
    int64_t v1 = kotoba_aiueos_qwen35_activation(xmode, a1p, bp, xc, xmode >= 5 ? h1p : 0);
    int64_t v2 = new_call(xmode, a2p, an, bp, bp ? xbn : 0, xmode >= 5 ? h2p : 0, xmode >= 5 ? hn : 0, xc);
    unsigned bad = v1 != v2;
    for (uint64_t i = 0; i < count; i++) if (a1[i] != a2[i]) bad++;
    for (uint64_t i = 0; i < 3 * count; i++) if (h1[i] != h2[i]) bad++;
    if (v1 >= -9 && v1 <= 0) seen[-v1]++;
    if (bad && n_bad++ < 8) { puts_("ACT-DIFF "); hex(k, 4); hex(mode, 1); hex((uint64_t)v1, 16); hex((uint64_t)v2, 16); hex(bad, 6); putc_('\n'); }
    if (k % 500 == 499) { puts_("AT "); hex(k + 1, 4); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 10; i++) { putc_(' '); hex(seen[i], 4); } putc_('\n');
  puts_("CASES 0c80 DIFFS "); hex(n_bad, 4); puts_("NEG9 "); hex(n_bad9, 4); putc_('\n'); puts_("DONE\n");
}
