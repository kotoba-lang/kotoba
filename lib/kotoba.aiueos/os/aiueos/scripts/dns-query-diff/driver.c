#include <stdint.h>
uint32_t old_build_dns_query(uint8_t *, uint32_t, uint32_t, uint16_t, const uint8_t *, uint32_t);
uint32_t new_build_dns_query(uint8_t *, uint32_t, uint32_t, uint16_t, const uint8_t *, uint32_t);
void old_set(const uint8_t *, const uint8_t *); void new_set(const uint8_t *, const uint8_t *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 1035;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 13; }
static uint8_t fa[1024], fb[1024], q[320];
static unsigned n_cases, n_built, n_bad;
void test_main(void) {
  puts_("DNSQUERYDIFF\n");
  const uint32_t edges[] = {0, 1, 4, 5, 6, 18, 24, 254, 255, 256, 300};
  for (unsigned k = 0; k < 6000; k++) {
    uint8_t mac[6], peer[6];
    for (int i = 0; i < 6; i++) { mac[i] = (uint8_t)rnd(); peer[i] = (uint8_t)rnd(); }
    old_set(mac, peer); new_set(mac, peer);
    uint32_t ql = k < 110 ? edges[k % 11] : 5 + (uint32_t)(rnd() % 251);
    for (uint32_t i = 0; i < ql; i++) q[i] = (uint8_t)(k % 4 ? 'a' + rnd() % 26 : rnd());
    for (int i = 0; i < 1024; i++) fa[i] = fb[i] = (uint8_t)(0x5a ^ i);
    uint32_t src = (uint32_t)rnd(), dst = (uint32_t)(k % 9 ? rnd() : 0), sport = (uint32_t)rnd();
    uint16_t port = (uint16_t)(k % 3 ? 53 : sport);
    uint32_t ra = old_build_dns_query(fa, src, dst, port, q, ql), rb = new_build_dns_query(fb, src, dst, port, q, ql);
    int same = ra == rb;
    for (int i = 0; i < 1024; i++) if (fa[i] != fb[i]) same = 0;
    n_cases++; if (ra) n_built++;
    if (!same && n_bad++ < 8) { puts_("DNSQ-DIFF "); hex(k, 4); hex(ql, 3); hex(ra, 3); hex(rb, 3); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("BUILT "); hex(n_built, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
