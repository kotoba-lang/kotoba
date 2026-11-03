#include <stdint.h>
int old_p256_did(const uint8_t public_key[64], char *out, uint32_t capacity);
extern int64_t kotoba_aiueos_p256_did(const uint8_t *, uint64_t, char *, uint64_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 67;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static unsigned n_cases, n_ok, n_bad, n_shown;
static uint8_t pub[64]; static char o1[200], o2[200];
static void one(uint32_t cap, unsigned tag) {
  int r1, r2, same;
  for (int i = 0; i < 200; i++) o1[i] = o2[i] = (char)(0x30 + (i % 40));
  r1 = old_p256_did(pub, o1, cap);
  r2 = (int)kotoba_aiueos_p256_did(pub, 64, o2, cap);
  same = r1 == r2; for (int i = 0; i < 200; i++) if (o1[i] != o2[i]) same = 0;
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; if (n_shown++ < 6) { puts_("DID-DIFF "); hex(tag, 4); hex(cap, 3); hex(r1, 1); hex(r2, 1); puts_(o1); putc_(' '); puts_(o2); putc_('\n'); } }
}
void test_main(void) {
  static const uint32_t caps[] = {0, 1, 9, 10, 48, 54, 55, 56, 57, 58, 59, 60, 64, 95, 96, 97, 199};
  puts_("DIDDIFF\n");
  for (unsigned k = 0; k < 400; k++) {
    for (int i = 0; i < 64; i++) pub[i] = (uint8_t)rnd();
    if (k == 0) for (int i = 0; i < 64; i++) pub[i] = 0;
    if (k == 1) for (int i = 0; i < 64; i++) pub[i] = 0xff;
    if (k % 7 == 2) for (int i = 0; i < (int)(k % 9); i++) pub[i] = 0;   /* X with leading zero bytes */
    if (k % 11 == 3) pub[0] = 0xff;
    for (unsigned c = 0; c < sizeof caps / 4; c++) one(caps[c], k);
  }
  {
    /* refused only by the object: a key length other than 64, a null output, a length with a non-zero upper half */
    unsigned bad = 0;
    for (int i = 0; i < 200; i++) o2[i] = 0x5a;
    if (kotoba_aiueos_p256_did(pub, 63, o2, 199)) bad++;
    if (kotoba_aiueos_p256_did(pub, 65, o2, 199)) bad++;
    if (kotoba_aiueos_p256_did(pub, 64, 0, 199)) bad++;
    if (kotoba_aiueos_p256_did(pub, 64, o2, 0x1000000c7ull)) bad++;
    for (int i = 0; i < 200; i++) if (o2[i] != 0x5a) bad++;
    n_cases += 4; n_bad += bad;
  }
  puts_("CASES "); hex(n_cases, 5); puts_("WHOLE "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
