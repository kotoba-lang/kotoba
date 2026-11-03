#include <stdint.h>
int old_cpu_random_bytes(uint8_t *, uint32_t);
uint64_t old_read_cycles(void);
extern int64_t kotoba_aiueos_cpu_random_bytes(uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_read_cycles(void);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint8_t b1[17000], b2[17000];
static unsigned n_cases, n_bad;
void test_main(void) {
  puts_("CPUREADSDIFF\n");
  /* read_cycles: the object's read lies between two C reads around it */
  for (int i = 0; i < 1000; i++) {
    uint64_t a = old_read_cycles(), t = (uint64_t)kotoba_aiueos_read_cycles(), c = old_read_cycles();
    n_cases++; if (!(a <= t && t <= c)) { n_bad++; puts_("CYCLES-DIFF "); hex(a, 16); hex(t, 16); hex(c, 16); putc_('\n'); }
  }
  /* random bytes: the same status, every byte written on success (it is not all the fill), nothing past n written */
  static const uint32_t sizes[] = {1, 7, 8, 9, 15, 16, 17, 32, 33, 64, 1000, 16384};
  unsigned ok = 0;
  for (unsigned k = 0; k < sizeof sizes / 4; k++) {
    uint32_t n = sizes[k];
    for (uint32_t i = 0; i < sizeof b1; i++) b1[i] = b2[i] = 0xa5;
    int r1 = old_cpu_random_bytes(b1, n), r2 = (int)kotoba_aiueos_cpu_random_bytes(b2, n);
    unsigned same_fill = 0, past = 0, untouched = 1;
    for (uint32_t i = 0; i < n; i++) { if (b2[i] == 0xa5) same_fill++; if (b2[i] != 0xa5) untouched = 0; }
    for (uint32_t i = n; i < sizeof b2; i++) if (b2[i] != 0xa5) past++;
    int good = r1 == r2 && past == 0 && (r2 ? (n < 8 || same_fill < n / 8 + 4) : untouched);
    n_cases++; if (r1) ok++;
    if (!good) { n_bad++; puts_("RAND-DIFF "); hex(n, 5); hex(r1, 1); hex(r2, 1); hex(same_fill, 5); hex(past, 5); putc_('\n'); }
  }
  /* refused: null, zero length (both); a length above 16384 (the object; the C has no bound) */
  n_cases += 3;
  if (old_cpu_random_bytes(0, 8) != (int)kotoba_aiueos_cpu_random_bytes(0, 8)) n_bad++;
  if (old_cpu_random_bytes(b1, 0) != (int)kotoba_aiueos_cpu_random_bytes(b2, 0)) n_bad++;
  if (kotoba_aiueos_cpu_random_bytes(b2, 16385)) n_bad++;
  puts_("CASES "); hex(n_cases, 4); puts_("RANDOM-OK "); hex(ok, 2); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
