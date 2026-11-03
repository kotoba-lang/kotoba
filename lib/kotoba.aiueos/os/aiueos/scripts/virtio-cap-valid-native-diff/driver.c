/* virtio-cap-valid built on amu's native object route against the committed kotoba-compiler/1 object (JUN-600). Both
   answer the same for every argument tuple: the full grid over each clause's boundary values (pointer, cap-length,
   bar, offset, length) and random tuples over boundary values (0, +-1, powers of two
   and their neighbours, 64/252/256, 2^32, 2^40, the i64 extremes) and random tuples mixing them with random values. */
#include <stdint.h>
extern int64_t kotoba_aiueos_virtio_cap_valid(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4);
extern int64_t kotoba_aiueos_virtio_cap_valid_native(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 600;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const int64_t V[] = {0, 1, -1, 2, 3, 4, 5, 6, 7, 15, 16, 19, 20, 63, 64, 65, 0xff, 0x100, 0xfff, 0x1000, 0x1001,
  0x38, 0x40, 236, 251, 252, 253, 255, 256, 0x7fffffff, 0x80000000ll, 0xfffffff0ll, 0xffffffffll, 0x100000000ll,
  1ll << 40, (1ll << 40) - 1, 1ll << 62, INT64_MAX, INT64_MIN, INT64_MIN + 1, -4096};
#define NV (sizeof V / sizeof V[0])
static unsigned n_bad, n_one, n_all;
static void one(const int64_t *v) {
  int64_t r1 = kotoba_aiueos_virtio_cap_valid(v[0], v[1], v[2], v[3], v[4]), r2 = kotoba_aiueos_virtio_cap_valid_native(v[0], v[1], v[2], v[3], v[4]);
  n_all++; if (r1 == 1) n_one++;
  if (r1 != r2 && n_bad++ < 10) { puts_("DIFF"); for (int i = 0; i < 5; i++) { putc_(' '); hex((uint64_t)v[i], 16); } hex((uint64_t)r1, 16); hex((uint64_t)r2, 16); putc_('\n'); }
}
static int64_t pick(void) { unsigned k = (unsigned)(rnd() % 4); return k == 0 ? (int64_t)rnd() : k == 1 ? (int64_t)(rnd() % 600) - 100 : V[rnd() % NV] + (int64_t)(rnd() % 3) - 1; }
void test_main(void) {
  int64_t v[5];
  puts_("SCALARDIFF\n");

  static const int64_t P[] = {-1, 0, 63, 64, 65, 200, 236, 240, 251, 252, 253, 256};
  static const int64_t C[] = {-1, 0, 15, 16, 20, 191, 192, 193};
  static const int64_t B[] = {-1, 0, 5, 6};
  static const int64_t O[] = {-1, 0, 0x1000, 0xfffffff0ll, 0xffffffffll, 0x100000000ll};
  static const int64_t L[] = {-1, 0, 1, 0xf, 0x10, 0x38, 0xffffffffll};
#define N(a) (sizeof a / sizeof a[0])
  for (unsigned p = 0; p < N(P); p++) for (unsigned c = 0; c < N(C); c++) for (unsigned b = 0; b < N(B); b++)
    for (unsigned o = 0; o < N(O); o++) for (unsigned l = 0; l < N(L); l++) {
      v[0] = P[p]; v[1] = C[c]; v[2] = B[b]; v[3] = O[o]; v[4] = L[l]; one(v); }
  for (unsigned k = 0; k < 40000; k++) { for (int i = 0; i < 5; i++) v[i] = pick(); one(v); }
  puts_("CASES "); hex(n_all, 8); puts_("ONE "); hex(n_one, 8); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
