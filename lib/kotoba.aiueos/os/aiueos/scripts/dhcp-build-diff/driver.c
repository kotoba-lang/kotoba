#include <stdint.h>
uint32_t old_build_dhcp(uint8_t *, uint8_t, uint32_t, uint32_t); uint32_t new_build_dhcp(uint8_t *, uint8_t, uint32_t, uint32_t);
void old_set(const uint8_t *); void new_set(const uint8_t *);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 2131;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 17; }
static uint8_t fa[512], fb[512];
static unsigned n_cases, n_req, n_bad;
void test_main(void) {
  puts_("DHCPBUILDDIFF\n");
  const uint8_t types[] = {1, 3, 0, 2, 5, 255};
  for (unsigned k = 0; k < 6000; k++) {
    uint8_t mac[6];
    for (int i = 0; i < 6; i++) mac[i] = (uint8_t)(k % 13 == 0 ? 0 : rnd());
    old_set(mac); new_set(mac);
    uint8_t type = k < 600 ? types[k % 6] : (k % 2 ? 1 : 3);
    uint32_t req = (uint32_t)(k % 17 ? rnd() : 0), srv = (uint32_t)(k % 19 ? rnd() : 0xffffffffu);
    for (int i = 0; i < 512; i++) fa[i] = fb[i] = (uint8_t)rnd();
    uint32_t ra = old_build_dhcp(fa, type, req, srv), rb = new_build_dhcp(fb, type, req, srv);
    int same = ra == rb; for (int i = 0; i < 512; i++) if (fa[i] != fb[i]) same = 0;
    n_cases++; if (type == 3) n_req++;
    if (!same && n_bad++ < 8) { puts_("DHCP-DIFF "); hex(k, 4); hex(type, 2); hex(ra, 3); hex(rb, 3); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 4); puts_("REQUESTS "); hex(n_req, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
