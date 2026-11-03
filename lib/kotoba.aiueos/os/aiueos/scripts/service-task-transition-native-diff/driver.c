/* service-task-transition built on amu's native object route against the committed kotoba-compiler/1 object (JUN-708). Both
   answer the same for every argument tuple: the full grid over a smaller boundary set over boundary values (0, +-1, powers of two
   and their neighbours, 64/252/256, 2^32, 2^40, the i64 extremes plus the values its clauses test (1ll << 32, (2ll << 32) + 5, 3ll << 32, (4ll << 32) + 77, 5ll << 32, 9)) and random tuples mixing them with random values. */
#include <stdint.h>
extern int64_t kotoba_aiueos_service_task_transition(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4);
extern int64_t kotoba_aiueos_service_task_transition_native(int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 708;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static const int64_t V[] = {0, 1, -1, 2, 3, 4, 5, 6, 7, 15, 16, 19, 20, 63, 64, 65, 0xff, 0x100, 0xfff, 0x1000, 0x1001,
  0x38, 0x40, 236, 251, 252, 253, 255, 256, 0x7fffffff, 0x80000000ll, 0xfffffff0ll, 0xffffffffll, 0x100000000ll,
  1ll << 40, (1ll << 40) - 1, 1ll << 62, INT64_MAX, INT64_MIN, INT64_MIN + 1, -4096, 1ll << 32, (2ll << 32) + 5, 3ll << 32, (4ll << 32) + 77, 5ll << 32, 9};
#define NV (sizeof V / sizeof V[0])
static const int64_t S[] __attribute__((unused)) = {0, 1, -1, 2, 3, 4, 5, 7, 8, 16, 63, 64, 0xff, 0x1000, 0xffffffffll, INT64_MAX, INT64_MIN, 1ll << 32, (2ll << 32) + 5, 3ll << 32, (4ll << 32) + 77, 5ll << 32, 9};
#define NS (sizeof S / sizeof S[0])
static unsigned n_bad, n_one, n_all;
static void one(const int64_t *v) {
  int64_t r1 = kotoba_aiueos_service_task_transition(v[0], v[1], v[2], v[3], v[4]), r2 = kotoba_aiueos_service_task_transition_native(v[0], v[1], v[2], v[3], v[4]);
  n_all++; if (r1 != 0) n_one++;
  if (r1 != r2 && n_bad++ < 10) { puts_("DIFF"); for (int i = 0; i < 5; i++) { putc_(' '); hex((uint64_t)v[i], 16); } hex((uint64_t)r1, 16); hex((uint64_t)r2, 16); putc_('\n'); }
}
static int64_t pick(void) { unsigned k = (unsigned)(rnd() % 4); return k == 0 ? (int64_t)rnd() : k == 1 ? (int64_t)(rnd() % 600) - 100 : V[rnd() % NV] + (int64_t)(rnd() % 3) - 1; }
void test_main(void) {
  int64_t v[5];
  puts_("SCALARDIFF\n");
  for (unsigned i0 = 0; i0 < NS; i0++)
  for (unsigned i1 = 0; i1 < NS; i1++)
  for (unsigned i2 = 0; i2 < NS; i2++)
  for (unsigned i3 = 0; i3 < NS; i3++)
  for (unsigned i4 = 0; i4 < NS; i4++)
    { v[0] = S[i0]; v[1] = S[i1]; v[2] = S[i2]; v[3] = S[i3]; v[4] = S[i4]; one(v); }
  for (unsigned k = 0; k < 40000; k++) { for (int i = 0; i < 5; i++) v[i] = pick(); one(v); }
  puts_("CASES "); hex(n_all, 8); puts_("NONZERO "); hex(n_one, 8); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
