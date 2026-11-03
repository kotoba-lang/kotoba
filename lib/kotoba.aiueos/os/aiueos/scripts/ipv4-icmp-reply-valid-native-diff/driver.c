/* ipv4-icmp-reply-valid built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object.
   Valid IPv4 ICMP echo replies (EtherType 0x0800, IHL 5, protocol 1, a right header checksum, the expected source; type
   0, code 0, a right ICMP checksum over the IPv4 total length less 20, odd lengths included, the expected identifier and
   sequence) with one field then mutated in turn -- the EtherType, IHL, total length (below 28 and past the frame), the
   protocol, either checksum, the source, type, code, identifier or sequence, or an expected argument -- and frame
   lengths at and around 42 and 2048, random frames and a null base; answers and traps compared. */
#include "diff.h"
#include "frames.h"
extern int64_t kotoba_aiueos_ipv4_icmp_reply_valid(int64_t, int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_ipv4_icmp_reply_valid_native(int64_t, int64_t, int64_t, int64_t, int64_t);
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)kotoba_aiueos_ipv4_icmp_reply_valid, *n = (void *)kotoba_aiueos_ipv4_icmp_reply_valid_native;
  for (unsigned k = 0; k < 20000; k++) {
    fill_random();
    uint32_t src = (uint32_t)rnd(), id = (uint32_t)(rnd() & 0xffff), sq = (uint32_t)(rnd() & 0xffff);
    uint32_t total = 28 + (uint32_t)(rnd() % 3 ? rnd() % 64 : rnd() % (2048 - 14 - 28 + 1));
    int64_t len = 14 + total + (int64_t)(rnd() % 3 ? 0 : rnd() % (2048 - 14 - total + 1));
    if (len < 42) len = 42;
    ipv4(total, 1, src, (uint32_t)rnd());
    frame[34] = 0; frame[35] = 0; be16(38, id); be16(40, sq); icmp_checksum(total - 20);
    int64_t es = src, ei = id, eq = sq;
    unsigned m = (unsigned)(rnd() % 12);
    if (m == 1) { static const int F[] = {12, 13, 14}; frame[F[rnd() % 3]] ^= (uint8_t)(1 + rnd() % 255); ip_checksum(); }
    if (m == 2) { be16(16, rnd() % 2 ? (uint32_t)(rnd() % 28) : (uint32_t)(len - 14 + 1 + rnd() % 4)); ip_checksum(); }
    if (m == 3) { frame[23] = (uint8_t)(rnd() % 2 ? 6 : 17); ip_checksum(); }
    if (m == 4) frame[24 + rnd() % 2] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 5) frame[36 + rnd() % 2] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 6) { frame[34 + rnd() % 2] = (uint8_t)(1 + rnd() % 8); icmp_checksum(total - 20); }
    if (m == 7) { frame[26 + rnd() % 4] ^= (uint8_t)(1 + rnd() % 255); ip_checksum(); }
    if (m == 8) { if (rnd() % 2) ei ^= 1u << (rnd() % 16); else eq ^= 1u << (rnd() % 17); }
    if (m == 9) es ^= 1ll << (rnd() % 33);
    if (m == 10) { static const int64_t L[] = {0, 33, 41, 42, 2048, 2049, -1}; len = L[rnd() % 7]; }
    if (m == 11) frame[34 + 8 + rnd() % (total - 28 + 1)] ^= (uint8_t)(1 + rnd() % 255);   /* a payload byte (or past it) */
    same(o, n, k % 211 == 0 ? 0 : b, len, es, ei, eq);
  }
  report();
}
