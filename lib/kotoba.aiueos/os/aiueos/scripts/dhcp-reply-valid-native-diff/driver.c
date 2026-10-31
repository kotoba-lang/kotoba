/* dhcp-reply-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. Valid
   DHCP replies (net-frames/dhcp.h: every reason-0 clause satisfied, with and without a UDP checksum) with one field then
   mutated so that each of the twelve refusal reasons is reached -- the length, the IPv4 envelope, the UDP ports, length
   and checksum, op/htype/hlen, XID, CHADDR, the cookie, a malformed option walk (an option running past the datagram, no
   END), a missing or wrong message type, server id, mask (and addresses invalid under it) and lease (below 60, above
   30 days) -- plus random frames and a null base; the reason code and traps compared. */
#include "diff.h"
#include "frames.h"
#include "dhcp.h"
extern int64_t kotoba_aiueos_dhcp_reply_valid(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_dhcp_reply_valid_native(int64_t, int64_t, int64_t, int64_t, int64_t);
static const uint32_t MASK[] = {0xffffff00u, 0xffff0000u, 0xff000000u, 0xfffffffcu, 0xfffffffeu, 0xffffffffu, 0xfeffff00u, 0x00ffffffu};
static unsigned reasons[16];
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)kotoba_aiueos_dhcp_reply_valid, *n = (void *)kotoba_aiueos_dhcp_reply_valid_native;
  for (unsigned k = 0; k < 30000; k++) {
    fill_random();
    uint32_t xid = (uint32_t)rnd(); uint64_t mac = (rnd() << 24 ^ rnd()) & 0xffffffffffffull; uint8_t type = (uint8_t)(rnd() % 2 ? 2 : 5);
    uint32_t mask = MASK[rnd() % 3], yi = (10u << 24) | ((uint32_t)rnd() & ~mask & 0xfffffe) | 1u;
    if (rnd() % 4 == 0) yi = (uint32_t)rnd();
    uint32_t lease = 60 + (uint32_t)(rnd() % 2592000);
    unsigned m = (unsigned)(rnd() % 16);
    if (m == 1) mask = MASK[rnd() % 8];
    if (m == 2) lease = (uint32_t)(rnd() % 2 ? rnd() % 61 : 2592000 + rnd() % 3 - 1);
    int64_t len = dhcp_frame(xid, mac, type, yi, mask, lease, rnd() % 4 == 0);
    if (rnd() % 3 == 0) len += (int64_t)(rnd() % (2049 - len));
    int64_t ex = xid, em = (int64_t)mac, et = type;
    if (m == 3) { static const int64_t L[] = {0, 282, 283, 2048, 2049, -1}; len = L[rnd() % 6]; }
    if (m == 4) { static const int F[] = {12, 13, 14, 16, 17, 23, 24}; frame[F[rnd() % 7]] ^= (uint8_t)(1 + rnd() % 255); if (rnd() % 2) ip_checksum(); }
    if (m == 5) { static const int F[] = {34, 35, 36, 37, 38, 39, 40, 41, 50}; frame[F[rnd() % 9]] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 6) frame[42 + rnd() % 3] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 7) { if (rnd() % 2) ex ^= 1ll << (rnd() % 33); else em ^= 1ll << (rnd() % 49); }
    if (m == 8) { frame[278 + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 9) { int at = 282; while (frame[at] == 0) at++; frame[at + 1 + 2 + frame[at + 1]] = 250; }   /* the second option's length runs past the datagram */
    if (m == 10) { for (int i = 282; i < 2048; i++) if (frame[i] == 255) { frame[i] = 0; break; } }       /* END turned into padding */
    if (m == 11) et = et == 2 ? 5 : 2;
    if (m == 12) { for (int i = 282; i < 400; i++) if (frame[i] == 54 && frame[i + 1] == 4) { frame[i] = 199; break; } }
    if (m == 13) { for (int i = 282; i < 400; i++) if (frame[i] == 51 && frame[i + 1] == 4) { frame[i + 1] = 3; break; } }
    if (m == 14) { for (int i = 282; i < 400; i++) if (frame[i] == 1 && frame[i + 1] == 4) { frame[i] = 199; break; } }
    if (m == 15) for (int i = 0; i < 300; i++) frame[i] = (uint8_t)rnd();
    if (m >= 8 && m <= 14 && frame[40] | frame[41]) { uint32_t udp = get16(38); l4_checksum(40, 17, udp); }   /* keep the UDP checksum right */
    same(o, n, k % 307 == 0 ? 0 : b, len, ex, em, et);
    if (!last_trap_old && last_old >= 0 && last_old < 16) reasons[last_old]++;
  }
  puts_("REASONS"); for (int i = 0; i < 13; i++) { putc_(' '); hex(reasons[i], 4); } putc_('\n');
  report();
}
