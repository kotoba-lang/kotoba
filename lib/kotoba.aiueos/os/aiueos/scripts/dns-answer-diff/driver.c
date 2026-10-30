#include <stdint.h>
int old_dns_answer_ok_named(const uint8_t *, uint32_t, uint32_t, uint32_t, uint16_t, const uint8_t *, uint32_t, uint32_t *);
int new_dns_answer_ok_named(const uint8_t *, uint32_t, uint32_t, uint32_t, uint16_t, const uint8_t *, uint32_t, uint32_t *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 53;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static uint8_t f[2048], q[300];
static uint32_t len, qlen, src, dst;
static uint16_t port;
static unsigned n_cases, n_ok, n_bad;
static void be16(uint32_t at, uint32_t v) { f[at] = (uint8_t)(v >> 8); f[at + 1] = (uint8_t)v; }
static void be32(uint32_t at, uint32_t v) { be16(at, v >> 16); be16(at + 2, v & 0xffff); }
static uint32_t sum(const uint8_t *p, uint32_t n, uint32_t acc) {
  for (uint32_t i = 0; i < n; i += 2) acc += (uint32_t)p[i] << 8 | (i + 1 < n ? p[i + 1] : 0);
  return acc;
}
static uint16_t fold(uint32_t s) { while (s >> 16) s = (s & 0xffff) + (s >> 16); return (uint16_t)s; }
static void checksums(int udp_zero) {
  uint32_t total = (uint32_t)f[16] << 8 | f[17], ul = (uint32_t)f[38] << 8 | f[39];
  be16(24, 0); be16(24, (uint16_t)~fold(sum(f + 14, 20, 0)));
  be16(40, 0);
  if (!udp_zero && 34 + ul <= 2048 && total) {
    uint32_t p = (src >> 16) + (src & 0xffff) + (dst >> 16) + (dst & 0xffff) + 17 + ul;
    uint16_t c = (uint16_t)~fold(sum(f + 34, ul, p));
    be16(40, c == 0 ? 0xffff : c);
  }
}
/* a well-formed answer: layout 0 the pointer form, 1 the copied question */
static void build(unsigned k) {
  qlen = 5 + (uint32_t)(rnd() % (k % 7 == 0 ? 251 : 40));
  for (uint32_t i = 0; i < qlen; i++) q[i] = (uint8_t)(k % 3 ? 'a' + rnd() % 26 : rnd());
  src = (uint32_t)rnd(); dst = (uint32_t)rnd(); port = (uint16_t)(k % 5 ? 53 : 5353 + rnd() % 100);
  unsigned layout = k & 1;
  uint32_t alen = layout ? qlen + 10 : 16, pad = k % 4 == 1 ? (uint32_t)(rnd() % 7) : 0;
  uint32_t total = 20 + 8 + 12 + qlen + alen + pad;
  if (14 + total > 2048) { pad = 0; total = 20 + 8 + 12 + qlen + alen; }
  for (uint32_t i = 0; i < 14 + total + 8; i++) f[i] = (uint8_t)rnd();
  be16(12, 0x0800); f[14] = 0x45; f[15] = 0; be16(16, total); be16(18, (uint32_t)rnd()); be16(20, 0x4000); f[22] = 64; f[23] = 17;
  be32(26, src); be32(30, dst);
  be16(34, port); be16(36, 49154); be16(38, total - 20);
  be16(42, 0xa1e0); be16(44, k % 9 == 2 ? 0x8580 : 0x8180); be16(46, 1); be16(48, 1 + (uint32_t)(rnd() % 3)); be16(50, 0); be16(52, 0);
  for (uint32_t i = 0; i < qlen; i++) f[54 + i] = q[i];
  uint32_t a = 54 + qlen, addr = k % 11 == 3 ? 0 : (uint32_t)rnd() | 1;
  if (!layout) { f[a] = 0xc0; f[a + 1] = 0x0c; be16(a + 2, 1); be16(a + 4, 1); be32(a + 6, 300); be16(a + 10, 4); be32(a + 12, addr); }
  else { for (uint32_t i = 0; i < qlen; i++) f[a + i] = q[i]; be16(a + qlen, 1); be16(a + qlen + 2, 1); be16(a + qlen + 4, 4); be32(a + qlen + 6, addr); }
  checksums(k % 6 == 0);
  len = 14 + total + (k % 8 == 5 ? (uint32_t)(rnd() % 8) : 0);
}
static void compare(uint32_t n, uint32_t ql, unsigned tag) {
  uint32_t a1 = 0x5a5a5a5a, a2 = 0x5a5a5a5a;
  int r1 = old_dns_answer_ok_named(f, n, src, dst, port, q, ql, &a1);
  int r2 = new_dns_answer_ok_named(f, n, src, dst, port, q, ql, &a2);
  n_cases++; if (r1) n_ok++;
  if (r1 != r2 || a1 != a2) { if (n_bad++ < 8) { puts_("DNS-DIFF "); hex(tag, 6); hex(n, 3); hex(r1, 1); hex(r2, 1); hex(a1, 8); hex(a2, 8); putc_('\n'); } }
}
void test_main(void) {
  puts_("DNSANSWERDIFF\n");
  for (unsigned k = 0; k < 1500; k++) {
    build(k);
    compare(len, qlen, k * 16);
    compare(len, qlen - 1 - (uint32_t)(rnd() % 2), k * 16 + 1);          /* a shorter question */
    if (k % 10 == 0) { compare(len, 4, k * 16 + 2); compare(len, 256, k * 16 + 3); }
    for (unsigned c = 0; c < 4; c++) if (len > 1) compare(len - 1 - (uint32_t)(rnd() % (len - 1)), qlen, k * 16 + 4); /* truncated */
    if (k % 5 == 0) {                                                    /* every byte flipped once */
      for (uint32_t i = 0; i < len; i++) { uint8_t s = f[i]; f[i] ^= (uint8_t)(1 + rnd() % 255); compare(len, qlen, k * 16 + 5); f[i] = s; }
    } else {
      for (unsigned c = 0; c < 24; c++) { uint32_t i = (uint32_t)(rnd() % len); uint8_t s = f[i]; f[i] ^= (uint8_t)(1 << (rnd() % 8)); compare(len, qlen, k * 16 + 6); f[i] = s; }
    }
    /* length fields moved by one, checksums recomputed so the move is what is tested */
    uint32_t total = (uint32_t)f[16] << 8 | f[17], ul = (uint32_t)f[38] << 8 | f[39];
    be16(16, total + 1); checksums(0); compare(len, qlen, k * 16 + 7); be16(16, total - 1); checksums(0); compare(len, qlen, k * 16 + 8); be16(16, total);
    be16(38, ul + 1); checksums(0); compare(len, qlen, k * 16 + 9); be16(38, ul - 1); checksums(0); compare(len, qlen, k * 16 + 10); be16(38, ul);
    be16(38, ul - 1); be16(16, total - 1); checksums(0); compare(len, qlen, k * 16 + 11); be16(38, ul); be16(16, total); checksums(k % 6 == 0);
    compare(len, qlen, k * 16 + 12);
  }
  puts_("CASES "); hex(n_cases, 6); puts_("ADMITTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
