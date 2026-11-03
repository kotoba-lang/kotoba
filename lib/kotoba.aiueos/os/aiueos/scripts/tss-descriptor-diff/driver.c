/* kotoba/tss-descriptor.o against the expression kernel/process.c's aiueos_process_initialize used (main 4528a70b,
   copied verbatim below as reference), JUN-599: for every admitted (base, limit) the object writes the same two words;
   for every refused one (out length, null out, zero or non-canonical base, limit outside 103..0xfffff) it answers 0
   and writes nothing. */
#include <stdint.h>
extern int64_t kotoba_aiueos_tss_descriptor_build(int64_t base, int64_t limit, int64_t out, int64_t out_length);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 599;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed ^ (seed >> 29); }
static uint64_t out[4];
static unsigned n_all, n_built, n_bad;
static void reference(uint64_t b, uint64_t limit, uint64_t *w) {
  w[0]=(limit & 0xffff) | ((b & 0xffffff)<<16) |
    (0x89ULL<<40) | ((limit & 0xf0000)<<32) | ((b & 0xff000000)<<32);
  w[1]=b>>32;
}
static int admitted(int64_t b, int64_t limit, int64_t olen) {
  return olen == 16 && b != 0 && b >= -(1ll << 47) && b < (1ll << 47) && limit >= 103 && limit <= 0xfffff;
}
static void one(int64_t b, int64_t limit, int64_t olen, int null_out) {
  out[0] = out[1] = out[2] = 0x5a5a5a5a5a5a5a5aull;
  int64_t r = kotoba_aiueos_tss_descriptor_build(b, limit, null_out ? 0 : (int64_t)(uintptr_t)out, olen);
  int want = !null_out && admitted(b, limit, olen); uint64_t w[2];
  unsigned bad = (r != want);
  if (want) { reference((uint64_t)b, (uint64_t)limit, w); bad += out[0] != w[0]; bad += out[1] != w[1]; n_built++; }
  else { bad += out[0] != 0x5a5a5a5a5a5a5a5aull; bad += out[1] != 0x5a5a5a5a5a5a5a5aull; }
  bad += out[2] != 0x5a5a5a5a5a5a5a5aull;
  n_all++;
  if (bad && n_bad++ < 10) { puts_("TSS-DIFF "); hex((uint64_t)b, 16); hex((uint64_t)limit, 8); hex((uint64_t)olen, 2); hex((uint64_t)r, 16); hex(out[0], 16); hex(out[1], 16); putc_('\n'); }
}
void test_main(void) {
  puts_("TSSDESCDIFF\n");
  static const int64_t B[] = {1, 0x1000, 0x12345678, 0xff000000ll, 0xffffffffll, 0x100000000ll, (1ll << 47) - 1,
    1ll << 47, -(1ll << 47), -(1ll << 47) - 1, -1, 0, INT64_MAX, INT64_MIN};
  static const int64_t L[] = {102, 103, 104, 0xffff, 0x10000, 0xfffff, 0x100000, -1, 0};
  for (unsigned i = 0; i < sizeof B / 8; i++) for (unsigned j = 0; j < sizeof L / 8; j++) {
    one(B[i], L[j], 16, 0); one(B[i], L[j], 8, 0); one(B[i], L[j], 16, 1); }
  for (unsigned k = 0; k < 20000; k++) {
    int64_t b = (int64_t)(rnd() >> 17); if (k & 1) b = -b;
    int64_t l = 103 + (int64_t)(rnd() % 0xfff9d);
    if (k % 97 == 0) b = (int64_t)rnd();
    one(b, l, k % 211 == 0 ? 17 : 16, 0);
  }
  puts_("CASES "); hex(n_all, 8); puts_("BUILT "); hex(n_built, 8); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
