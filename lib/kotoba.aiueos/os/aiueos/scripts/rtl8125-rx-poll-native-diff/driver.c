/* rtl8125-rx-poll built on amu's native object route (JUN-708) against the committed kotoba-compiler/1 object. The
   native export takes the descriptor's length after the descriptor (the old one had none and read through a literal
   32-byte window), so the old object is called as (desc capacity) and the native one as (desc 32 capacity), and each
   native call is repeated with a length other than 32, which must answer -1 (AIUEOS_RTL8125_INVALID, negated) without
   reading. Receive command words: OWN set or clear, every combination of RX_ERROR/SOF/EOF, lengths 0..20, near the
   capacity and random; descriptors at a 256-aligned base, a misaligned one or null; capacities 0..2049, the kernel's
   2048 or random. Answers, traps (through the #UD guard) and the descriptor bytes are compared. */
#include "diff.h"
extern int64_t kotoba_aiueos_rtl8125_rx_poll(int64_t, int64_t);
extern int64_t kotoba_aiueos_rtl8125_rx_poll_native(int64_t, int64_t, int64_t);
static uint8_t m0[768] __attribute__((aligned(256))), m1[768] __attribute__((aligned(256)));
static unsigned n_len, n_len_bad, n_frames, n_rxinv, n_owned;
void test_main(void) {
  guard_init(); puts_("RXPOLLDIFF\n");
  void *o = (void *)kotoba_aiueos_rtl8125_rx_poll, *n = (void *)kotoba_aiueos_rtl8125_rx_poll_native;
  for (unsigned k = 0; k < 20000; k++) {
    for (int i = 0; i < 768; i++) m0[i] = (uint8_t)rnd();
    unsigned b = (unsigned)(rnd() % 12);
    int64_t off = b < 9 ? 256 : b < 11 ? 256 + 4 * (int64_t)(1 + rnd() % 63) : -1;
    unsigned c = (unsigned)(rnd() % 6);
    int64_t cap = c < 3 ? 2048 : c == 3 ? (int64_t)(rnd() % 2051) - 1 : c == 4 ? (int64_t)(rnd() % 4) + 2046 : (int64_t)rnd();
    uint32_t cmd = (uint32_t)rnd();
    if (rnd() % 4) {
      cmd &= ~0x83103fffu; cmd |= (uint32_t)(rnd() % 4 == 0) << 31;
      if (rnd() % 3) cmd |= 0x03000000u; else cmd |= (uint32_t)(rnd() % 4) << 24;
      if (rnd() % 6 == 0) cmd |= 0x00100000u;
      unsigned l = (unsigned)(rnd() % 5);
      uint32_t len = l == 0 ? (uint32_t)(rnd() % 21) : l == 1 ? (uint32_t)(cap & 0x3fff) + (uint32_t)(rnd() % 3) - 1 : (uint32_t)(rnd() % 0x4000);
      cmd |= len & 0x3fff;
    }
    if (off >= 0) for (int i = 0; i < 4; i++) m0[off + 28 + i] = (uint8_t)(cmd >> (8 * i));
    for (int i = 0; i < 768; i++) m1[i] = m0[i];
    int64_t base = off < 0 ? 0 : (int64_t)(uintptr_t)(m0 + off);
    int64_t r1 = guarded_call(o, base, cap, 0, 0, 0); int t1 = (int)guard_trapped;
    int64_t r2 = guarded_call(n, base, 32, cap, 0, 0); int t2 = (int)guard_trapped;
    int eq = r1 == r2 && t1 == t2;
    for (int i = 0; i < 768; i++) if (m1[i] != m0[i]) eq = 0;
    n_all++; if (t1) n_trap++; else if (r1 != 0) n_nz++;
    if (!t1) { if (r1 > 0) n_frames++; else if (r1 == -6) n_rxinv++; else if (r1 == 0) n_owned++; }
    if (!eq && n_bad++ < 10) { puts_("DIFF "); hex(k, 4); hex((uint64_t)r1, 16); hex((uint64_t)t1, 1); hex((uint64_t)r2, 16); hex((uint64_t)t2, 1); putc_('\n'); }
    int64_t bad = rnd() % 2 ? (int64_t)(rnd() % 64) : (int64_t)rnd(); if (bad == 32) bad = 33;
    int64_t r3 = guarded_call(n, base, bad, cap, 0, 0); int t3 = (int)guard_trapped;
    n_len++; if (r3 != -1 || t3) { if (n_len_bad++ < 4) { puts_("LENDIFF "); hex(k, 4); hex((uint64_t)r3, 16); putc_('\n'); } }
  }
  puts_("FRAMES "); hex(n_frames, 8); puts_("RXINVALID "); hex(n_rxinv, 8); puts_("OWNED "); hex(n_owned, 8); putc_('\n');
  puts_("LENGTHS "); hex(n_len, 8); puts_("LENDIFFS "); hex(n_len_bad, 4); putc_('\n');
  if (n_len_bad) n_bad++;
  report();
}
