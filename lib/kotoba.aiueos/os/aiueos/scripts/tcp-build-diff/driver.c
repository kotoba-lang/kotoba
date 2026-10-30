#include <stdint.h>
uint32_t old_build_tcp(uint8_t *, uint32_t, uint32_t, uint16_t, uint16_t, uint32_t, uint32_t, uint8_t, const uint8_t *, uint32_t);
uint32_t new_build_tcp(uint8_t *, uint32_t, uint32_t, uint16_t, uint16_t, uint32_t, uint32_t, uint8_t, const uint8_t *, uint32_t);
void old_set(const uint8_t *, const uint8_t *, uint16_t, uint16_t); void new_set(const uint8_t *, const uint8_t *, uint16_t, uint16_t);
uint16_t old_ip_id(void); uint16_t new_ip_id(void);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 6;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
static uint8_t fa[4096], fb[4096], pay[4096];
static unsigned n_cases, n_bad, n_refused_sum;
void test_main(void) {
  puts_("TCPBUILDDIFF\n");
  const uint32_t lens[] = {0, 1, 2, 3, 8, 142, 1460, 1981, 1982, 1983, 1993, 1994, 2015, 2016, 2017, 2100, 4000};
  for (unsigned k = 0; k < 6000; k++) {
    uint8_t mac[6], peer[6];
    for (int i = 0; i < 6; i++) { mac[i] = (uint8_t)rnd(); peer[i] = (uint8_t)rnd(); }
    uint16_t window = (uint16_t)rnd(), id = (uint16_t)(k % 50 == 0 ? 0xffff : rnd());
    old_set(mac, peer, window, id); new_set(mac, peer, window, id);
    uint32_t plen = k < 170 ? lens[k % 17] : (k % 3 ? (uint32_t)(rnd() % 200) : (uint32_t)(rnd() % 2040));
    for (uint32_t i = 0; i < plen; i++) pay[i] = (uint8_t)rnd();
    for (int i = 0; i < 4096; i++) fa[i] = fb[i] = (uint8_t)(0xa5 ^ i);
    uint32_t src = (uint32_t)rnd(), dst = (uint32_t)(k % 7 ? rnd() : 0xffffffffu), seq = (uint32_t)rnd(), ack = (uint32_t)rnd();
    uint16_t sp = (uint16_t)rnd(), dp = (uint16_t)(k % 5 ? rnd() : 443);
    uint8_t flags = (uint8_t)rnd();
    uint32_t ra = old_build_tcp(fa, src, dst, sp, dp, seq, ack, flags, plen ? pay : 0, plen);
    uint32_t rb = new_build_tcp(fb, src, dst, sp, dp, seq, ack, flags, plen ? pay : 0, plen);
    int same = ra == rb && old_ip_id() == new_ip_id();
    for (int i = 0; i < 4096; i++) if (fa[i] != fb[i]) same = 0;
    if (32 + plen > 2048) n_refused_sum++;
    n_cases++;
    if (!same && n_bad++ < 8) { puts_("TCP-DIFF "); hex(k, 4); hex(plen, 4); hex(ra, 4); hex(rb, 4); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("OVERSIZE "); hex(n_refused_sum, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
