/* qwen35-rope rebuilt on amu's native root against the committed kotoba-compiler/1 object (JUN-633, JUN-554): the same
   source, two compilers. kotoba_aiueos_qwen35_rope (the committed object, as the kernel links it) and
   kotoba_aiueos_qwen35_rope_native (the source compiled by the native root under a test name) rotate the same heads
   and must answer the same and leave the same bits. 3000 calls: heads 1..8, 4, 24 (the two call sites) and 64 (the
   limit), positions over 0..25735 with both ends, values random or with +-0, +-inf, NaNs, denormals and extremes mixed
   in; and the refusals -- a null pointer, heads 0 and 65, a byte count that is not heads * 1024, positions -1 and
   25736. */
#include <stdint.h>
extern uint64_t kotoba_aiueos_qwen35_rope(float *values, uint64_t values_bytes, uint64_t heads, uint64_t position);
extern uint64_t kotoba_aiueos_qwen35_rope_native(float *values, uint64_t values_bytes, uint64_t heads, uint64_t position);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t base[64 * 256] __attribute__((aligned(64))), a[64 * 256] __attribute__((aligned(64))),
  b[64 * 256] __attribute__((aligned(64)));
static uint64_t seed = 2633;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const uint32_t special[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0x7fc12345u,
  0x7f800001u, 0x00000001u, 0x807fffffu, 0x7f7fffffu, 0xff7fffffu, 0x3f800000u, 0xbf800000u};
static uint32_t pick(int specials) {
  if (specials && rnd() % 6 == 0) return special[rnd() % (sizeof special / sizeof special[0])];
  uint32_t m = (uint32_t)rnd() & 0x807fffffu, e = (uint32_t)(100 + rnd() % 56) << 23;   /* about 2^-27 .. 2^28 */
  return m | e;
}
void test_main(void) {
  puts_("ROPENATIVEDIFF\n");
  unsigned n_bad = 0, n_ok = 0, n_refused = 0;
  for (unsigned k = 0; k < 3000; k++) {
    unsigned r = (unsigned)(rnd() % 20);
    uint64_t heads = r < 14 ? 1 + rnd() % 8 : r < 16 ? 4 : r < 18 ? 24 : 64;
    uint64_t position = k % 50 == 0 ? 0 : k % 50 == 1 ? 25735 : rnd() % 25736;
    uint64_t bytes = heads * 1024; float *ptr = (float *)a; float *ptr2 = (float *)b;
    if (k % 97 == 0) { ptr = 0; ptr2 = 0; }
    if (k % 89 == 0) heads = 0;
    if (k % 83 == 0) heads = 65;
    if (k % 79 == 0) bytes += 4;
    if (k % 73 == 0) position = (uint64_t)-1;
    if (k % 71 == 0) position = 25736;
    int specials = k % 3 == 0;
    unsigned n = (unsigned)((heads >= 1 && heads <= 64 ? heads : 1) * 256);
    for (unsigned i = 0; i < n; i++) base[i] = pick(specials);
    for (unsigned i = 0; i < n; i++) { a[i] = base[i]; b[i] = base[i]; }
    uint64_t r1 = kotoba_aiueos_qwen35_rope(ptr, bytes, heads, position);
    uint64_t r2 = kotoba_aiueos_qwen35_rope_native(ptr2, bytes, heads, position);
    unsigned bad = r1 != r2; for (unsigned i = 0; i < n; i++) if (a[i] != b[i]) bad++;
    if (r1 == 0) n_ok++; else n_refused++;
    if (bad && n_bad++ < 8) { puts_("ROPE-DIFF "); hex(k, 4); hex(r1, 4); hex(r2, 4); hex(heads, 2); hex(position, 5); hex(bad, 4); putc_('\n'); }
    if (k % 500 == 499) { puts_("AT "); hex(k + 1, 4); putc_('\n'); }
  }
  puts_("CASES "); hex(3000, 4); puts_("ROTATED "); hex(n_ok, 4); puts_("REFUSED "); hex(n_refused, 4);
  puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
