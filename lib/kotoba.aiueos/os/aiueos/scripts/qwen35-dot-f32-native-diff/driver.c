/* qwen35-dot-f32 ported to amu's native object route against the committed kotoba-compiler/1 object (JUN-633,
   JUN-554). kotoba_aiueos_qwen35_dot_f32 (the committed object) and kotoba_aiueos_qwen35_dot_f32_native (the ported
   source compiled by the native root under a test name) take the same vectors and must answer the same 64-bit word
   (a binary32 sum's bits, or a refusal). 4000 calls: counts 0..300 (every remainder mod 4), 4096 and 65536 (the
   limit), values random over a wide range or with +-0, +-inf, NaNs and denormals mixed in, and the refusals -- count
   -1 and 65537, a or b's length not count * 4. */
#include <stdint.h>
extern uint64_t kotoba_aiueos_qwen35_dot_f32(const void *a, uint64_t an, const void *b, uint64_t bn, uint64_t count);
extern uint64_t kotoba_aiueos_qwen35_dot_f32_native(const void *a, uint64_t an, const void *b, uint64_t bn, uint64_t count);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t va[65536] __attribute__((aligned(64))), vb[65536] __attribute__((aligned(64)));
static uint64_t seed = 360;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const uint32_t special[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0x7fc12345u,
  0x00000001u, 0x807fffffu, 0x7f7fffffu, 0x3f800000u};
static uint32_t pick(int specials) {
  if (specials && rnd() % 40 == 0) return special[rnd() % (sizeof special / sizeof special[0])];
  return ((uint32_t)rnd() & 0x807fffffu) | (uint32_t)(100 + rnd() % 56) << 23;
}
void test_main(void) {
  puts_("DOTF32DIFF\n");
  unsigned n_bad = 0, n_sum = 0, n_refused = 0;
  for (unsigned k = 0; k < 4000; k++) {
    uint64_t count = k % 400 == 0 ? 65536 : k % 400 == 1 ? 4096 : rnd() % 301;
    uint64_t an = count * 4, bn = count * 4;
    if (k % 97 == 0) count = (uint64_t)-1;
    if (k % 89 == 0) count = 65537;
    if (k % 83 == 0) an += 4;
    if (k % 79 == 0) bn -= 4;
    unsigned n = count <= 65536 ? (unsigned)count : 0; int specials = k % 3 == 0;
    for (unsigned i = 0; i < n; i++) { va[i] = pick(specials); vb[i] = pick(specials); }
    uint64_t r1 = kotoba_aiueos_qwen35_dot_f32(va, an, vb, bn, count);
    uint64_t r2 = kotoba_aiueos_qwen35_dot_f32_native(va, an, vb, bn, count);
    if ((int64_t)r1 < -4294967296ll) n_refused++; else n_sum++;
    if (r1 != r2 && n_bad++ < 8) { puts_("DOT-DIFF "); hex(k, 4); hex(count, 5); hex(r1, 16); hex(r2, 16); putc_('\n'); }
  }
  puts_("CASES "); hex(4000, 4); puts_("SUMS "); hex(n_sum, 4); puts_("REFUSED "); hex(n_refused, 4);
  puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
