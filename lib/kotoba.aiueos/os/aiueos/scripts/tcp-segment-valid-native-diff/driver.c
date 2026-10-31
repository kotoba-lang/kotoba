/* tcp-segment-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid IPv4 TCP segments (EtherType 0x0800, IHL 5, protocol 6, a right header checksum, the expected source; a right TCP
   checksum with the pseudo header over the IPv4 total length less 20, odd lengths included; the expected
   acknowledgement and flags) with one field then mutated in turn -- the EtherType, IHL, total length (below 40 and past
   the frame), the protocol, either checksum, a pseudo-header address, a payload byte, the source, acknowledgement or
   flags or an expected argument -- and frame lengths at and around 54 and 2048, random frames and a null base; answers
   and traps compared. */
#include "diff.h"
#include "frames.h"
#include "tcp.h"
extern int64_t kotoba_aiueos_tcp_segment_valid(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_tcp_segment_valid_native(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)kotoba_aiueos_tcp_segment_valid, *n = (void *)kotoba_aiueos_tcp_segment_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    fill_random();
    uint32_t src = (uint32_t)rnd(), ack = (uint32_t)rnd(); uint8_t fl = (uint8_t)rnd();
    uint32_t total = 40 + (uint32_t)(rnd() % 3 ? rnd() % 200 : rnd() % (2048 - 14 - 40 + 1));
    int64_t len = 14 + total + (int64_t)(rnd() % 3 ? 0 : rnd() % (2048 - 14 - total + 1));
    tcp_segment(total, src, ack, fl);
    int64_t es = src, ea = ack, ef = fl;
    unsigned m = (unsigned)(rnd() % 12);
    if (m == 1) { static const int F[] = {12, 13, 14}; frame[F[rnd() % 3]] ^= (uint8_t)(1 + rnd() % 255); ip_checksum(); }
    if (m == 2) { be16(16, rnd() % 2 ? (uint32_t)(rnd() % 40) : (uint32_t)(len - 14 + 1 + rnd() % 4)); ip_checksum(); }
    if (m == 3) { frame[23] = (uint8_t)(rnd() % 2 ? 1 : 17); ip_checksum(); }
    if (m == 4) frame[24 + rnd() % 2] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 5) frame[50 + rnd() % 2] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 6) { frame[30 + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255); ip_checksum(); }    /* destination: pseudo header only */
    if (m == 7) frame[54 + rnd() % (total - 40 + 1)] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 8) { if (rnd() % 2) ea ^= 1ll << (rnd() % 33); else ef ^= 1 << (rnd() % 9); }
    if (m == 9) es ^= 1ll << (rnd() % 33);
    if (m == 10) { static const int64_t L[] = {0, 41, 53, 54, 55, 2048, 2049, -1}; len = L[rnd() % 8]; }
    if (m == 11) { frame[42 + rnd() % 6] ^= (uint8_t)(1 + rnd() % 255); }                  /* ack/offset/flags, stale checksum */
    same(o, n, k % 211 == 0 ? 0 : b, len, es, ea, ef);
  }
  report();
}
