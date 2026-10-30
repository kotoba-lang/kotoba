/* qwen35-norm ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633, JUN-554).
   The two take different arguments -- the old (mode, a, b, c, d) with b a weight pointer in mode 0 and a head count
   in modes 1..3; the new (mode | heads << 8, a, a-length, w, w-length, o, o-length, count) -- so each call is made
   to each in its own form, with the lengths the shape gives, on copies of the same values, weights and output, and
   must answer the same and leave the same bytes. 3000 calls: the four modes, counts / widths 1..300 and the limits
   (65536; heads * width 262144), values random or with +-0, +-inf, NaNs, huge values whose squares overflow (mode 2's
   max-abs fallback) and zeros, and each old refusal (-1 null values, -2 a mode past 3, -3 a count outside 1..65536,
   -4 heads outside 1..4096 or heads * width past 262144, -5 a null weight or output). 200 more calls give the new
   object a length the shape does not give and must be refused with -9. */
#include <stdint.h>
extern int64_t kotoba_aiueos_qwen35_norm(uint64_t mode, uint64_t a, uint64_t b, uint64_t c, uint64_t d);
extern int64_t kotoba_aiueos_qwen35_norm_native(uint64_t mh, uint64_t a, uint64_t an, uint64_t w, uint64_t wn,
                                                uint64_t o, uint64_t on, uint64_t count);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
#define MAXN 262144
static uint32_t va0[MAXN], va1[MAXN], va2[MAXN], vw[65536], vo1[65536], vo2[65536];
static uint64_t seed = 697;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static uint32_t val(unsigned kind) {
  static const uint32_t sp[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0x00000001u};
  if (kind == 1 && rnd() % 40 == 0) return sp[rnd() % 6];
  if (kind == 2) return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(200 + rnd() % 50) << 23;   /* squares overflow */
  if (kind == 3 && rnd() % 3 == 0) return 0;
  return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(110 + rnd() % 30) << 23;
}
void test_main(void) {
  puts_("NORMDIFF\n");
  unsigned n_bad = 0, seen[10] = {0}, n_bad9 = 0;
  for (unsigned k = 0; k < 3200; k++) {
    uint64_t mode = k % 4, heads = 1 + rnd() % 8, c = 1 + rnd() % 300;
    if (k % 97 == 0) { c = mode == 0 ? 65536 : 64; heads = mode == 0 ? 1 : 4096; }
    unsigned kind = (unsigned)(rnd() % 4);
    uint64_t n = mode == 0 ? c : heads * c;
    if (n > MAXN) n = MAXN;
    for (uint64_t i = 0; i < n; i++) va0[i] = val(kind);
    for (uint64_t i = 0; i < 65536 && i < (mode == 0 ? c : c); i++) vw[i] = val(kind == 2 ? 0 : kind);
    for (uint64_t i = 0; i < n; i++) { va1[i] = va0[i]; va2[i] = va0[i]; }
    for (uint64_t i = 0; i < c && i < 65536; i++) { vo1[i] = 0x5a5a5a5au; vo2[i] = 0x5a5a5a5au; }
    uint64_t a1 = (uint64_t)(uintptr_t)va1, a2 = (uint64_t)(uintptr_t)va2, w = (uint64_t)(uintptr_t)vw;
    uint64_t o1 = (uint64_t)(uintptr_t)vo1, o2 = (uint64_t)(uintptr_t)vo2;
    uint64_t an = n * 4, wn = c * 4, on = mode == 0 ? c * 4 : 0, xmode = mode, xc = c, xheads = heads;
    unsigned r = k % 29;
    if (k >= 3000) {                                   /* the new object only: a length the shape does not give */
      int64_t v = kotoba_aiueos_qwen35_norm_native(mode | heads << 8, a2, an + 4, w, mode == 1 ? 0 : wn, mode == 0 ? o2 : 0,
                                                   on, c);
      if (v != -9 && n_bad9++ < 4) { puts_("NEG9-DIFF "); hex(k, 4); hex((uint64_t)v, 16); putc_('\n'); }
      continue;
    }
    if (r == 1) { a1 = 0; a2 = 0; }
    if (r == 2) xmode = 4 + rnd() % 3;
    if (r == 3) xc = 0;
    if (r == 4) xc = 65537;
    if (r == 5 && mode) xheads = 0;
    if (r == 6 && mode) xheads = 4097;
    if (r == 7 && mode) { xheads = 4096; xc = 65; }
    if (r == 8) { w = 0; if (mode == 0) o1 = o2 = (uint64_t)(uintptr_t)vo1; }
    if (r == 9 && mode == 0) { o1 = 0; o2 = 0; }
    if (r >= 2 && r <= 7) { an = (mode == 0 ? xc : xheads * xc) * 4; wn = xc * 4; on = mode == 0 ? xc * 4 : 0; }
    int64_t v1 = xmode == 0 ? kotoba_aiueos_qwen35_norm(0, a1, w, xc, o1)
                            : kotoba_aiueos_qwen35_norm(xmode, a1, xheads, xc, xmode == 1 ? 0 : w);
    int64_t v2 = kotoba_aiueos_qwen35_norm_native(xmode | xheads << 8, a2, an, xmode == 1 ? 0 : w, xmode == 1 ? 0 : wn,
                                                  xmode == 0 ? o2 : 0, xmode == 0 ? on : 0, xc);
    unsigned bad = v1 != v2;
    for (uint64_t i = 0; i < n; i++) if (va1[i] != va2[i]) bad++;
    for (uint64_t i = 0; i < c && i < 65536; i++) if (vo1[i] != vo2[i]) bad++;
    if (v1 >= -9 && v1 <= 0) seen[-v1]++;
    if (bad && n_bad++ < 8) { puts_("NORM-DIFF "); hex(k, 4); hex(mode, 1); hex((uint64_t)v1, 16); hex((uint64_t)v2, 16); hex(bad, 6); putc_('\n'); }
    if (k % 500 == 499) { puts_("AT "); hex(k + 1, 4); putc_('\n'); }
  }
  puts_("VERDICTS"); for (int i = 0; i < 10; i++) { putc_(' '); hex(seen[i], 4); } putc_('\n');
  puts_("CASES 0c80 DIFFS "); hex(n_bad, 4); puts_("NEG9 "); hex(n_bad9, 4); putc_('\n'); puts_("DONE\n");
}
