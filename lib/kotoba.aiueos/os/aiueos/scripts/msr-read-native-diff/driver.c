/* msr-read built on amu's native object route (JUN-552, amu ADR 0399) against the committed kotoba-compiler/1 object.
   Both are linked into one image and called through the #UD guard on the same index: the five admitted indices, the
   unlisted neighbours of each (IA32_CSTAR 0xc0000083 between two admitted ones among them), the architectural MSRs
   the kernel does not read, the i64 extremes, the admitted indices plus 2^32 (which a uint32_t would truncate), and
   random 32- and 64-bit indices. Before each round the C writes fresh STAR / LSTAR / FMASK values (bit 63 set in half of
   them), so the admitted reads return varied 64-bit values. Answers and trap outcomes must agree. */
#include <stdint.h>
#include "diff.h"
extern int64_t kotoba_aiueos_msr_read(int64_t);
extern int64_t kotoba_aiueos_msr_read_native(int64_t);
static void wrmsr(uint32_t i, uint64_t v) { __asm__ volatile("wrmsr" :: "c"(i), "a"((uint32_t)v), "d"((uint32_t)(v >> 32))); }
static uint64_t rnd64(void) { return rnd() << 40 ^ rnd() << 20 ^ rnd(); }
static const int64_t FIXED[] = {27, 3221225600, 3221225601, 3221225602, 3221225604,
  0, 1, 16, 26, 28, 0x1a0, 0x277, 0x3a, 0x10, 0xc0000079, 0xc000007f, 0xc0000083, 0xc0000085, 0xc0000086, 0xc0000100,
  0xc0000101, 0xc0000102, 0xc0000103, -1, -27, INT64_MIN, INT64_MAX, (1ll << 32) + 27, (1ll << 32) + 3221225600,
  (1ll << 32) + 3221225604, 4294967295, 2147483648, 3221225600 - (1ll << 32)};
void test_main(void) {
  guard_init();
  puts_("MSRREAD\n");
  for (int round = 0; round < 64; round++) {
    uint64_t a = rnd64() & 0x7fffffffffffull;
    wrmsr(0xc0000081, rnd64()); wrmsr(0xc0000082, (round & 1) ? a : (a | 0xffff800000000000ull)); wrmsr(0xc0000084, rnd64() & 0xffffffffull);
    for (unsigned k = 0; k < sizeof FIXED / 8; k++) same(kotoba_aiueos_msr_read, kotoba_aiueos_msr_read_native, FIXED[k], 0, 0, 0, 0);
    for (int k = 0; k < 16; k++) { same(kotoba_aiueos_msr_read, kotoba_aiueos_msr_read_native, (int64_t)(rnd() & 0xffffffffu), 0, 0, 0, 0);
      same(kotoba_aiueos_msr_read, kotoba_aiueos_msr_read_native, (int64_t)rnd64(), 0, 0, 0, 0); }
  }
  wrmsr(0xc0000081, 0); wrmsr(0xc0000082, 0); wrmsr(0xc0000084, 0);
  report();
}
