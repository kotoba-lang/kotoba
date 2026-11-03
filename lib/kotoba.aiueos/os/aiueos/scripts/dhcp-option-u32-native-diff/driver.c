/* dhcp-option-u32 built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. Valid
   DHCP replies (net-frames/dhcp.h) asked for each option they carry with a 4-byte value (server id, mask, lease, DNS,
   router), for options carried at another length (message type, an unknown option) or not carried, and for pad and
   END; with one field then mutated in turn -- the length, EtherType, IHL, protocol, IPv4 total length, the cookie, an
   option length running past the datagram, END turned into padding -- plus random frames and a null base; answers and
   traps compared. */
#include "diff.h"
#include "frames.h"
#include "dhcp.h"
extern int64_t kotoba_aiueos_dhcp_option_u32(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_dhcp_option_u32_native(int64_t, int64_t, int64_t);
static const int64_t CODE[] = {54, 1, 51, 6, 3, 53, 200, 0, 255, 2, 50, 300, -1};
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)kotoba_aiueos_dhcp_option_u32, *n = (void *)kotoba_aiueos_dhcp_option_u32_native;
  for (unsigned k = 0; k < 30000; k++) {
    fill_random();
    int64_t len = dhcp_frame((uint32_t)rnd(), rnd(), 5, (uint32_t)rnd(), 0xffffff00u, (uint32_t)rnd(), 1);
    if (rnd() % 3 == 0) len += (int64_t)(rnd() % (2049 - len));
    int64_t code = CODE[rnd() % 13];
    unsigned m = (unsigned)(rnd() % 10);
    if (m == 1) { static const int64_t L[] = {0, 282, 283, 2048, 2049, -1}; len = L[rnd() % 6]; }
    if (m == 2) { static const int F[] = {12, 13, 14, 23}; frame[F[rnd() % 4]] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 3) be16(16, rnd() % 2 ? 267 - (uint32_t)(rnd() % 3) : (uint32_t)(len - 14 + 1 + rnd() % 3));
    if (m == 4) frame[278 + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 5) { int at = 282; while (frame[at] == 0) at++; frame[at + 1 + 2 + frame[at + 1]] = 250; }
    if (m == 6) { for (int i = 282; i < 2048; i++) if (frame[i] == 255) { frame[i] = 0; break; } }
    if (m == 7) for (int i = 0; i < 300; i++) frame[i] = (uint8_t)rnd();
    same(o, n, k % 307 == 0 ? 0 : b, len, code, 0, 0);
  }
  report();
}
