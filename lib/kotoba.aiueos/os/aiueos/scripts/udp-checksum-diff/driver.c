#include <stdint.h>
uint16_t old_udp_checksum(const uint8_t *, uint32_t); uint16_t new_udp_checksum(const uint8_t *, uint32_t);
int old_udp_rx_checksum_ok(const uint8_t *, uint32_t); int new_udp_rx_checksum_ok(const uint8_t *, uint32_t);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 768;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 15; }
static uint8_t f[2200];
static unsigned n_cases, n_ok, n_bad;
static void compare(uint32_t ul, unsigned tag) {
  uint16_t t1 = old_udp_checksum(f, ul), t2 = new_udp_checksum(f, ul);
  int r1 = old_udp_rx_checksum_ok(f, ul), r2 = new_udp_rx_checksum_ok(f, ul);
  n_cases++; if (r1) n_ok++;
  if (t1 != t2 || r1 != r2) { if (n_bad++ < 8) { puts_("UDP-DIFF "); hex(tag, 5); hex(ul, 4); hex(t1, 4); hex(t2, 4); hex(r1, 1); hex(r2, 1); putc_('\n'); } }
}
void test_main(void) {
  puts_("UDPCHECKSUMDIFF\n");
  const uint32_t edges[] = {0, 1, 2, 7, 8, 9, 300, 548, 2034, 2035, 2036, 2037, 2100, 2160};
  for (unsigned k = 0; k < 8000; k++) {
    uint32_t ul = k < 140 ? edges[k % 14] : (k % 4 ? (uint32_t)(rnd() % 700) : (uint32_t)(rnd() % 2100));
    for (uint32_t i = 0; i < 34 + ul; i++) f[i] = (uint8_t)(k % 9 == 0 ? (rnd() & 1 ? 0xff : 0) : rnd());
    compare(ul, k * 4);
    if (ul >= 8) {                                   /* the checksum field set to what a sender would write */
      f[40] = f[41] = 0;
      uint16_t c = old_udp_checksum(f, ul);
      f[40] = (uint8_t)(c >> 8); f[41] = (uint8_t)c;
      compare(ul, k * 4 + 1);
      f[34 + (uint32_t)(rnd() % ul)] ^= (uint8_t)(1 << (rnd() % 8));   /* one bit off */
      compare(ul, k * 4 + 2);
    }
  }
  puts_("CASES "); hex(n_cases, 5); puts_("RX-OK "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
