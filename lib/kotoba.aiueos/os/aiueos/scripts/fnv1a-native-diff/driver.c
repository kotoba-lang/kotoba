/* fnv1a built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object: both read the
   same buffer and must answer the same. FNV-1a over random buffers of 0 .. 512 bytes (and 128, the kernel's one length), every answer compared in all 64 bits.
   512 is the native route's bound for a plain kernel-load-u8 window (amu ADR 0373): the native object traps from 513
   bytes, where the old object answered; the kernel only ever hashes 128. */
#include <stdint.h>
extern int64_t kotoba_aiueos_fnv1a(int64_t base, int64_t length);
extern int64_t kotoba_aiueos_fnv1a_native(int64_t base, int64_t length);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 552;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static uint8_t buf[4104] __attribute__((aligned(16)));
static unsigned n_all, n_nz, n_bad;
static void one(int64_t base, int64_t len) {
  int64_t r1 = kotoba_aiueos_fnv1a(base, len), r2 = kotoba_aiueos_fnv1a_native(base, len);
  n_all++; if (r1 != 0) n_nz++;
  if (r1 != r2 && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)len, 8); hex((uint64_t)r1, 16); hex((uint64_t)r2, 16); putc_('\n'); }
}
void test_main(void) {
  puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  static const int64_t L[] = {0, 1, 2, 7, 8, 9, 127, 128, 129, 255, 256, 511, 512};
  for (unsigned k = 0; k < 3000; k++) {
    int64_t len = k < 13 * 20 ? L[k % 13] : (int64_t)(rnd() % 513);
    for (int64_t i = 0; i < len; i++) buf[i] = (uint8_t)rnd();
    if (k % 50 == 0) for (int64_t i = 0; i < len; i++) buf[i] = (uint8_t)(k & 1 ? 0xff : 0);
    one(b, len);
  }
  puts_("CASES "); hex(n_all, 8); puts_("NONZERO "); hex(n_nz, 8); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
