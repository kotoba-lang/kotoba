/* net-arp-reply-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid ARP replies (EtherType 0x0806, Ethernet/IPv4, sizes 6 and 4, operation 2, the sender address expected) with one
   field then mutated in turn -- the EtherType, each ARP header field, the sender address or the expected one -- and
   lengths at and around 42 and 2048, random frames, and a null base; answers and traps compared. */
#include "diff.h"
#include "frames.h"
extern int64_t kotoba_aiueos_net_arp_reply_valid(int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_net_arp_reply_valid_native(int64_t, int64_t, int64_t);
static const int64_t LEN[] = {0, 1, 31, 32, 41, 42, 43, 60, 2047, 2048, 2049, -1, INT64_MIN};
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)kotoba_aiueos_net_arp_reply_valid, *n = (void *)kotoba_aiueos_net_arp_reply_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    fill_random();
    uint32_t ip = (uint32_t)rnd();
    be16(12, 0x0806); be16(14, 1); be16(16, 0x0800); frame[18] = 6; frame[19] = 4; be16(20, 2); be32(28, ip);
    int64_t len = 42 + (int64_t)(rnd() % 2007), want = ip;
    unsigned m = (unsigned)(rnd() % 8);
    if (m == 1) { static const int F[] = {12, 13, 14, 15, 16, 17, 18, 19, 20, 21}; frame[F[rnd() % 10]] ^= (uint8_t)(1 + rnd() % 255); }
    if (m == 2) frame[28 + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 3) want = rnd() % 2 ? ip ^ (1u << (rnd() % 32)) : (int64_t)ip | (1ll << 32);
    if (m == 4) len = LEN[rnd() % 13];
    if (m == 5) for (int i = 0; i < 42; i++) frame[i] = (uint8_t)rnd();
    if (m == 6) { be16(20, 1); }
    same(o, n, k % 211 == 0 ? 0 : b, len, want, 0, 0);
  }
  report();
}
