/* tcp-checksum-ok built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object. The
   native export takes the frame's extent after the frame; it is called with 2048, as both kernel callers do, and the old
   object without it. Valid IPv4 TCP segments (the TCP checksum right for the pseudo header of the source and destination
   arguments, over the IPv4 total length argument less 20, odd lengths included) with one input then mutated in turn --
   the checksum, a payload or header byte, the source or destination argument, the total length (below 40, past 2014,
   negative, huge) -- random frames, and a null base; answers and traps compared. */
#include "diff.h"
#include "frames.h"
#include "tcp.h"
extern int64_t kotoba_aiueos_tcp_checksum_ok(int64_t, int64_t, int64_t, int64_t);
extern int64_t kotoba_aiueos_tcp_checksum_ok_native(int64_t, int64_t, int64_t, int64_t, int64_t);
/* the old object's four arguments, with an unused fifth for guarded_call */
static int64_t old5(int64_t f, int64_t t, int64_t s, int64_t d, int64_t z) { (void)z; return kotoba_aiueos_tcp_checksum_ok(f, t, s, d); }
static int64_t new5(int64_t f, int64_t t, int64_t s, int64_t d, int64_t z) { (void)z; return kotoba_aiueos_tcp_checksum_ok_native(f, 2048, t, s, d); }
void test_main(void) {
  guard_init(); puts_("BUFDIFF\n");
  int64_t b = (int64_t)(uintptr_t)frame;
  void *o = (void *)old5, *n = (void *)new5;
  for (unsigned k = 0; k < 20000; k++) {
    fill_random();
    uint32_t src = (uint32_t)rnd(), dst = (uint32_t)rnd();
    uint32_t total = 40 + (uint32_t)(rnd() % 3 ? rnd() % 200 : rnd() % (2048 - 14 - 40 + 1));
    tcp_segment(total, src, (uint32_t)rnd(), (uint8_t)rnd()); be32(30, dst); l4_checksum(50, 6, total - 20);
    int64_t t = total, s = src, d = dst;
    unsigned m = (unsigned)(rnd() % 8);
    if (m == 1) frame[50 + rnd() % 2] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 2) frame[34 + rnd() % (total - 20)] ^= (uint8_t)(1 + rnd() % 255);
    if (m == 3) s ^= 1ll << (rnd() % 32);
    if (m == 4) d ^= 1ll << (rnd() % 32);
    if (m == 5) { static const int64_t T[] = {0, 39, 40, 41, 2013, 2014, 2015, 2034, -1, INT64_MIN, 1ll << 40}; t = T[rnd() % 11]; }
    if (m == 6) t = total + 1 + (int64_t)(rnd() % 3);
    if (m == 7) for (int i = 34; i < 54; i++) frame[i] = (uint8_t)rnd();
    same(o, n, k % 211 == 0 ? 0 : b, t, s, d, 0);
  }
  report();
}
