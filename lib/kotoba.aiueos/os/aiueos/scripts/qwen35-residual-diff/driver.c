/* The qwen35 residual add (JUN-554): old_add (the C loop, verbatim, as the kernel compiles it: vectorized SSE) and
   new_add (residual_add over kotoba/qwen35-residual.o, scalar addss per element, two per 64-bit access, in 4096-float
   chunks) from the same 5120-float state and addend must leave the same bits. 600 vectors: random binary32 patterns,
   and special values mixed in -- +-0, +-inf, quiet and signalling NaNs with payloads, denormals, the extremes, and
   near-cancelling pairs. */
#include <stdint.h>
void old_add(float *, const float *); int new_add(float *, const float *);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t s0[5120] __attribute__((aligned(64))), x0[5120] __attribute__((aligned(64)));
static uint32_t s1[5120] __attribute__((aligned(64))), s2[5120] __attribute__((aligned(64)));
static uint64_t seed = 1012;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const uint32_t special[] = {0x00000000u, 0x80000000u, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0xffc00000u,
  0x7fc12345u, 0x7f800001u, 0xff812345u, 0x00000001u, 0x807fffffu, 0x00400000u, 0x7f7fffffu, 0xff7fffffu,
  0x00800000u, 0x3f800000u, 0xbf800000u};
static uint32_t pick(void) {
  unsigned r = (unsigned)(rnd() % 8);
  if (r == 0) return special[rnd() % (sizeof special / sizeof special[0])];
  if (r == 1) return (uint32_t)rnd() & 0x807fffffu;                         /* denormal or zero */
  return (uint32_t)rnd();
}
void test_main(void) {
  puts_("RESIDUALDIFF\n");
  unsigned n_bad = 0, n_elems_bad = 0, n_refused = 0;
  for (unsigned k = 0; k < 600; k++) {
    for (int i = 0; i < 5120; i++) {
      s0[i] = pick(); x0[i] = pick();
      if (rnd() % 16 == 0) x0[i] = s0[i] ^ 0x80000000u;                    /* exact cancellation */
      if (rnd() % 16 == 0) x0[i] = (s0[i] ^ 0x80000000u) + (uint32_t)(rnd() % 3);   /* near-cancelling */
    }
    for (int i = 0; i < 5120; i++) { s1[i] = s0[i]; s2[i] = s0[i]; }
    old_add((float *)s1, (const float *)x0);
    if (!new_add((float *)s2, (const float *)x0)) n_refused++;
    unsigned bad = 0; for (int i = 0; i < 5120; i++) if (s1[i] != s2[i]) bad++;
    n_elems_bad += bad;
    if (bad && n_bad++ < 8) { puts_("RESID-DIFF "); hex(k, 3); hex(bad, 4); putc_('\n'); }
  }
  puts_("VECTORS "); hex(600, 4); puts_("ELEMENTS "); hex(600u * 5120u, 8); puts_("REFUSED "); hex(n_refused, 4);
  puts_("DIFFS "); hex(n_bad, 4); hex(n_elems_bad, 8); putc_('\n'); puts_("DONE\n");
}
