/* acpi-checksum-ok built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object: both read the
   same buffer and must answer the same. Random tables of 1 .. 16384 bytes, half with the last byte set so the byte sum is 0 mod 256, and every refusal (null or negative base, zero, negative and 16385 lengths). */
#include <stdint.h>
extern int64_t kotoba_aiueos_acpi_checksum_ok(int64_t base, int64_t length);
extern int64_t kotoba_aiueos_acpi_checksum_ok_native(int64_t base, int64_t length);
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 552;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static uint8_t buf[16392] __attribute__((aligned(16)));
static unsigned n_all, n_nz, n_bad;
static void one(int64_t base, int64_t len) {
  int64_t r1 = kotoba_aiueos_acpi_checksum_ok(base, len), r2 = kotoba_aiueos_acpi_checksum_ok_native(base, len);
  n_all++; if (r1 != 0) n_nz++;
  if (r1 != r2 && n_bad++ < 10) { puts_("DIFF "); hex((uint64_t)len, 8); hex((uint64_t)r1, 16); hex((uint64_t)r2, 16); putc_('\n'); }
}
void test_main(void) {
  puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)buf;
  static const int64_t L[] = {1, 7, 8, 9, 15, 16, 36, 44, 100, 4096, 16383, 16384};
  for (unsigned k = 0; k < 4000; k++) {
    int64_t len = k < 12 * 20 ? L[k % 12] : 1 + (int64_t)(rnd() % 16384);
    unsigned sum = 0;
    for (int64_t i = 0; i < len; i++) { buf[i] = (uint8_t)rnd(); sum += buf[i]; }
    if (k & 1) { sum -= buf[len - 1]; buf[len - 1] = (uint8_t)(0u - sum); }
    one(b, len);
  }
  one(0, 36); one(b, 0); one(b, -1); one(b, 16385); one(-4096, 36);
  puts_("CASES "); hex(n_all, 8); puts_("NONZERO "); hex(n_nz, 8); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
