#include <stdint.h>
uint32_t old_build_arp_request(uint8_t *); uint32_t new_build_arp_request(uint8_t *);
uint32_t old_build_icmp_echo(uint8_t *); uint32_t new_build_icmp_echo(uint8_t *);
void old_set(const uint8_t *, const uint8_t *); void new_set(const uint8_t *, const uint8_t *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 826;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 19; }
static uint8_t fa[128], fb[128];
static unsigned n_cases, n_bad;
static void cmp(unsigned tag, uint32_t ra, uint32_t rb) {
  int same = ra == rb; for (int i = 0; i < 128; i++) if (fa[i] != fb[i]) same = 0;
  n_cases++; if (!same && n_bad++ < 8) { puts_("ARP-ICMP-DIFF "); hex(tag, 5); hex(ra, 2); hex(rb, 2); putc_('\n'); }
}
void test_main(void) {
  puts_("ARPICMPDIFF\n");
  for (unsigned k = 0; k < 4000; k++) {
    uint8_t mac[6], peer[6];
    for (int i = 0; i < 6; i++) { mac[i] = (uint8_t)(k % 7 == 0 ? 0xff : rnd()); peer[i] = (uint8_t)(k % 11 == 0 ? 0 : rnd()); }
    old_set(mac, peer); new_set(mac, peer);
    for (int i = 0; i < 128; i++) fa[i] = fb[i] = (uint8_t)rnd();
    cmp(k * 2, old_build_arp_request(fa), new_build_arp_request(fb));
    for (int i = 0; i < 128; i++) fa[i] = fb[i] = (uint8_t)rnd();
    cmp(k * 2 + 1, old_build_icmp_echo(fa), new_build_icmp_echo(fb));
  }
  puts_("CASES "); hex(n_cases, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
