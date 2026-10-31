/* mmio-map-admit built on amu's native object route against the committed kotoba-compiler/1 object (JUN-600). Both
   answer the same admission for every (address, length): a grid over each clause's boundary (0, 1 GiB, each 1 GiB
   boundary, 2^40, the i64 extremes; lengths 0, 1, 2 MiB, 1 GiB +- 1, negatives) and random pairs near the
   boundaries. */
#include <stdint.h>
extern int64_t kotoba_aiueos_mmio_map_admit(int64_t address, int64_t length);
extern int64_t kotoba_aiueos_mmio_map_admit_native(int64_t address, int64_t length);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 600;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
#define G (1ll << 30)
static const int64_t A[] = {0, 1, G - 1, G, G + 1, 2 * G - 0x200000, 2 * G - 1, 2 * G, 0x7ff00000, 0xfe000000,
  0xfebf0000, 3 * G - 4096, (1ll << 40) - G, (1ll << 40) - 0x200000, (1ll << 40) - 1, 1ll << 40, (1ll << 40) + 1,
  INT64_MAX, -1, INT64_MIN, -G};
static const int64_t L[] = {0, 1, -1, 4096, 0x200000, G - 1, G, G + 1, 2 * G, 1ll << 62, INT64_MIN, INT64_MAX};
#define NA (sizeof A / sizeof A[0])
#define NL (sizeof L / sizeof L[0])
static unsigned n_bad, n_yes, n_all;
static void one(int64_t a, int64_t l) {
  int64_t v1 = kotoba_aiueos_mmio_map_admit(a, l), v2 = kotoba_aiueos_mmio_map_admit_native(a, l);
  n_all++; if (v1 == 1) n_yes++;
  if (v1 != v2 && n_bad++ < 10) { puts_("MA-DIFF "); hex((uint64_t)a, 16); hex((uint64_t)l, 16); hex((uint64_t)v1, 2); hex((uint64_t)v2, 2); putc_('\n'); }
}
void test_main(void) {
  puts_("MMIOADMITDIFF\n");
  for (unsigned i = 0; i < NA; i++) for (unsigned j = 0; j < NL; j++) one(A[i], L[j]);
  for (unsigned k = 0; k < 4000; k++) {
    int64_t a = (int64_t)(rnd() % 1100) * (G / 1024) + (int64_t)(rnd() % 3) - 1;
    int64_t l = (int64_t)(rnd() % (unsigned)(2 * G)) - 4096;
    one(a, l);
  }
  puts_("CASES "); hex(n_all, 4); puts_("ADMITTED "); hex(n_yes, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
