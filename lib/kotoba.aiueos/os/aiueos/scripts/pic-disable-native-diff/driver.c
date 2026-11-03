/* pic-disable built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. Every pair
   of master and slave vector bases from a set holding each admissible base (multiples of 8 in 40 .. 240 but 128) and
   the refusals around them (32, 128, 248, the neighbours of each bound, misaligned, negative and huge values); the
   answer of every call goes to debugcon, and run.sh compares the two runs' traces of every port write (the ICWs and
   OCWs to 0x20/0x21/0xa0/0xa1, the 0x80 waits) and read. Built once per object (NATIVE selects the native one). */
#include <stdint.h>
extern int64_t kotoba_aiueos_pic_disable(int64_t, int64_t);
extern int64_t kotoba_aiueos_pic_disable_native(int64_t, int64_t);
#ifdef NATIVE
#define CALL kotoba_aiueos_pic_disable_native
#else
#define CALL kotoba_aiueos_pic_disable
#endif
static void outb(uint16_t p, uint8_t v) { __asm__ volatile("outb %0, %1" :: "a"(v), "Nd"(p)); }
static uint8_t inb(uint16_t p) { uint8_t v; __asm__ volatile("inb %1, %0" : "=a"(v) : "Nd"(p)); return v; }
static void putc_(char c) { outb(0xe9, (uint8_t)c); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static int64_t S[64]; static unsigned ns;
void test_main(void) {
  puts_("PORTDIFF\n");
  static const int64_t X[] = {0, 1, 7, 8, 24, 31, 32, 33, 39, 41, 44, 127, 128, 129, 136, 241, 247, 248, 249, 255, 256, 264,
    -8, -1, 1ll << 32, (1ll << 32) + 40, INT64_MIN, INT64_MAX};
  for (int64_t b = 40; b <= 240; b += 8) if (b != 128) S[ns++] = b;
  for (unsigned i = 0; i < sizeof X / sizeof X[0]; i++) S[ns++] = X[i];
  unsigned n_all = 0, n_ok = 0;
  for (unsigned i = 0; i < ns; i++) {
    for (unsigned j = 0; j < ns; j++) {
      int64_t r = CALL(S[i], S[j]);
      n_all++; if (r) n_ok++;
      putc_("0123456789abcdef"[r & 15]);
      if (r) { (void)inb(0x21); (void)inb(0xa1); }   /* the masks it left, read back into the trace */
    }
    putc_('\n');
  }
  puts_("CASES "); hex(n_all, 8); puts_("NONZERO "); hex(n_ok, 8); putc_('\n'); puts_("DONE\n");
}
