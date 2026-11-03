#include <stdint.h>
void old_prepare(void); int old_has_avx2(void);
extern int64_t kotoba_aiueos_prepare_extended_state(void), kotoba_aiueos_cpu_has_avx2(void);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t rd_cr4(void) { uint64_t v; __asm__ volatile("mov %%cr4, %0" : "=r"(v)); return v; }
static void wr_cr4(uint64_t v) { __asm__ volatile("mov %0, %%cr4" : : "r"(v) : "memory"); }
static uint64_t rd_xcr0(void) { uint32_t lo, hi; __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0)); return ((uint64_t)hi << 32) | lo; }
static void wr_xcr0(uint64_t v) { __asm__ volatile("xsetbv" : : "a"((uint32_t)v), "d"((uint32_t)(v >> 32)), "c"(0)); }
void test_main(void) {
  puts_("XSTATESETUPDIFF\n");
  uint64_t cr4 = rd_cr4();
  /* the C's has_avx2 before prepare (XCR0 not yet enabled, or XSAVE off so xgetbv would #UD -- has_avx2 checks OSXSAVE first) */
  int a0 = old_has_avx2(), b0 = (int)kotoba_aiueos_cpu_has_avx2();
  old_prepare();
  uint64_t a_cr4 = rd_cr4(), a_xcr0 = (a_cr4 >> 18) & 1 ? rd_xcr0() : 0;
  int a1 = old_has_avx2();
  /* restore the start state: XCR0 back to x87 only, then CR4 */
  if ((a_cr4 >> 18) & 1) wr_xcr0(1);
  wr_cr4(cr4);
  int64_t did = kotoba_aiueos_prepare_extended_state();
  uint64_t b_cr4 = rd_cr4(), b_xcr0 = (b_cr4 >> 18) & 1 ? rd_xcr0() : 0;
  int b1 = (int)kotoba_aiueos_cpu_has_avx2();
  unsigned bad = (a0 != b0) + (a_cr4 != b_cr4) + (a_xcr0 != b_xcr0) + (a1 != b1) + ((did != 0) != (a_cr4 != cr4));
  puts_("BEFORE "); hex(a0, 1); hex(b0, 1); puts_("CR4 "); hex(a_cr4, 8); hex(b_cr4, 8); puts_("XCR0 "); hex(a_xcr0, 8); hex(b_xcr0, 8);
  puts_("AVX2 "); hex(a1, 1); hex(b1, 1); putc_('\n');
  puts_("DIFFS "); hex(bad, 2); putc_('\n'); puts_("DONE\n");
}
