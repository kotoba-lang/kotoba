#include <stdint.h>
uint64_t old_row_bytes(uint32_t, uint64_t);
extern int64_t kotoba_aiueos_qwen35_row_bytes(uint64_t, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 61;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed; }
static unsigned n_cases, n_ok, n_bad;
static void one(uint32_t type, uint64_t e) {
  uint64_t a = old_row_bytes(type, e), b = (uint64_t)kotoba_aiueos_qwen35_row_bytes(type, e);
  n_cases++; if (a) n_ok++;
  if (a != b) { n_bad++; if (n_bad < 10) { puts_("RB-DIFF "); hex(type, 3); hex(e, 16); hex(a, 16); hex(b, 16); putc_('\n'); } }
}
void test_main(void) {
  static const uint64_t edges[] = {0, 1, 2, 16, 31, 32, 33, 48, 64, 4112, 255, 256, 257, 512, 768, 4096, 5120, 17408, 248320,
    0x3fffffffffffffffull, 0x4000000000000000ull, 0x4000000000000020ull, 0x7fffffffffffff00ull, 0x8000000000000000ull,
    0x8000000000000100ull, 0xffffffffffffff00ull, 0xffffffffffffffe0ull, 0xffffffffffffffffull,
    0x0100000000000000ull, 0x00ffffffffffff00ull, 0x0200000000000000ull, 0x1000000000000000ull};
  puts_("ROWBYTESDIFF\n");
  for (uint32_t t = 0; t < 300; t++) {
    for (unsigned i = 0; i < sizeof edges / 8; i++) one(t, edges[i]);
    for (unsigned k = 0; k < 40; k++) { uint64_t r = rnd(); one(t, r); one(t, r & ~255ull); one(t, (r >> (rnd() & 63)) & ~31ull); }
  }
  /* types with bits above the low 8, as a uint32_t can carry */
  for (unsigned k = 0; k < 2000; k++) { uint32_t t = (uint32_t)rnd(); one(t, rnd() & ~255ull); one(t | 8u, 4096); }
  puts_("CASES "); hex(n_cases, 6); puts_("SIZED "); hex(n_ok, 6); puts_("DIFFS "); hex(n_bad, 6); putc_('\n'); puts_("DONE\n");
}
