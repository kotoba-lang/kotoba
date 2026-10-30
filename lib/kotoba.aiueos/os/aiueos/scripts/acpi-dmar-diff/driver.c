#include <stdint.h>
int old_parse(const uint8_t *); void old_state(uint64_t[4]);
int new_parse(const uint8_t *); void new_state(uint64_t[4]);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 79;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 9; }
static unsigned n_cases, n_ok, n_found, n_bad;
static uint8_t t[8192] __attribute__((aligned(8)));
static uint32_t len;
static void put16(uint32_t at, uint32_t v) { t[at] = (uint8_t)v; t[at + 1] = (uint8_t)(v >> 8); }
static void put64(uint32_t at, uint64_t v) { for (int i = 0; i < 8; i++) t[at + i] = (uint8_t)(v >> (8 * i)); }
/* one DRHD with a few device scopes; returns its length */
static uint32_t drhd(uint32_t at, uint16_t seg, uint64_t base, uint8_t flags) {
  uint32_t l = 16, scopes = (uint32_t)(rnd() % 4);
  for (uint32_t s = 0; s < scopes; s++) {
    uint32_t path = (uint32_t)(rnd() % 3) * 2 + (rnd() % 9 == 0 ? 1 : 0), sl = 6 + path;   /* now and then an odd path */
    t[at + l] = (uint8_t)(1 + rnd() % 4); t[at + l + 1] = (uint8_t)sl;
    for (uint32_t i = 2; i < sl; i++) t[at + l + i] = (uint8_t)rnd();
    l += sl;
  }
  put16(at, 0); put16(at + 2, l); t[at + 4] = flags; t[at + 5] = 0; put16(at + 6, seg); put64(at + 8, base);
  return l;
}
static uint32_t other(uint32_t at) {
  uint32_t l = 8 + (uint32_t)(rnd() % 24);
  put16(at, 1 + (uint32_t)(rnd() % 6)); put16(at + 2, l); for (uint32_t i = 4; i < l; i++) t[at + i] = (uint8_t)rnd();
  return l;
}
static void build(unsigned k) {
  for (int i = 0; i < 8192; i++) t[i] = 0;
  t[0] = 'D'; t[1] = 'M'; t[2] = 'A'; t[3] = 'R';
  static const uint8_t widths[] = {30, 31, 63, 64};
  t[36] = (uint8_t)(k % 17 == 0 ? rnd() % 80 : k % 17 == 1 ? widths[(k / 17) % 4] : 38 + rnd() % 10);   /* host address width */
  t[37] = (uint8_t)rnd();
  uint32_t at = 48, n = 1 + (uint32_t)(rnd() % 6);
  for (uint32_t s = 0; s < n && at < 7000; s++) {
    if (rnd() % 3) {
      uint64_t base = (rnd() & 0xffffffffff000ull);
      if (k % 13 == 1 && s == 0) base = 0;
      if (k % 13 == 2) base |= 0x10;
      if (k % 13 == 3) base |= 1ull << 52;
      if (k % 13 == 4) base |= 1ull << 63;
      at += drhd(at, (uint16_t)(rnd() % 4 == 0 ? 1 + rnd() % 3 : 0), base, (uint8_t)rnd());
    } else at += other(at);
  }
  len = at;
  if (k % 11 == 5) len -= (uint32_t)(1 + rnd() % 6);                 /* truncated */
  if (k % 11 == 6 && len > 60) t[48 + 2] = (uint8_t)(t[48 + 2] + 1 + rnd() % 3);   /* first structure's length off */
  if (k % 11 == 7 && len > 70) t[64 + 1] = (uint8_t)(rnd() % 9);      /* a scope length */
  if (k % 11 == 8) len = 36 + (uint32_t)(rnd() % 14);                 /* shorter than header + 12 */
  if (k % 19 == 9) t[(uint32_t)(48 + rnd() % (len > 49 ? len - 48 : 1))] ^= (uint8_t)(1 + rnd() % 255);
  t[4] = (uint8_t)len; t[5] = (uint8_t)(len >> 8); t[6] = 0; t[7] = 0;
}
void test_main(void) {
  puts_("DMARDIFF\n");
  for (unsigned k = 0; k < 4000; k++) {
    build(k);
    uint64_t a[4], b[4];
    int r1 = old_parse(t); old_state(a);
    int r2 = new_parse(t); new_state(b);
    int same = r1 == r2; for (int i = 0; i < 4; i++) if (a[i] != b[i]) same = 0;
    n_cases++; if (r1) n_ok++; if (a[1]) n_found++;
    if (!same) { n_bad++; if (n_bad < 8) { puts_("DMAR-DIFF "); hex(k, 4); hex(len, 4); hex(r1, 1); hex(r2, 1); hex(a[0], 2); hex(b[0], 2); hex(a[1], 16); hex(b[1], 16); putc_('\n'); } }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("ACCEPTED "); hex(n_ok, 4); puts_("FOUND "); hex(n_found, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
