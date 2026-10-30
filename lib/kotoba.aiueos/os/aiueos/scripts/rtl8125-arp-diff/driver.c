#include <stdint.h>
#include "rtl8125.h"
int rtl8125_handoff_model(void);
extern int64_t kotoba_aiueos_rtl8125_arp_request(const uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t,
                                                 uint64_t, uint64_t);
extern int64_t kotoba_aiueos_rtl8125_arp_reply(uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t,
                                               uint64_t, uint64_t);
/* kernel/rtl8125.c's two ARP helpers as they were, verbatim (only renamed) */
static void bytes_zero(void *value, uint32_t bytes) { uint8_t *p = value; while (bytes--) *p++ = 0; }
static uint16_t load_be16(const uint8_t *at) { return (uint16_t)(((uint16_t)at[0] << 8) | at[1]); }
static uint32_t load_be32(const uint8_t *at) { return ((uint32_t)at[0] << 24) | ((uint32_t)at[1] << 16) | ((uint32_t)at[2] << 8) | at[3]; }
static void store_be16(uint8_t *at, uint16_t value) { at[0] = (uint8_t)(value >> 8); at[1] = (uint8_t)value; }
static void store_be32(uint8_t *at, uint32_t value) { at[0] = (uint8_t)(value >> 24); at[1] = (uint8_t)(value >> 16); at[2] = (uint8_t)(value >> 8); at[3] = (uint8_t)value; }
static int mac_equal(const uint8_t *left, const uint8_t *right) { uint8_t difference = 0; for (unsigned i = 0; i < 6; i++) difference |= left[i] ^ right[i]; return difference == 0; }
static int mac_broadcast(const uint8_t *mac) { uint8_t all = 0xff; for (unsigned i = 0; i < 6; i++) all &= mac[i]; return all == 0xff; }
static int ref_request(const uint8_t *frame, uint32_t frame_length, const uint8_t local_mac[6], const uint8_t peer_mac[6],
                       uint32_t local_ip, uint32_t peer_ip) {
  if (!frame || !local_mac || !peer_mac || frame_length < 42U || !local_ip || !peer_ip) return 0;
  if ((!mac_broadcast(frame) && !mac_equal(frame, local_mac)) || !mac_equal(frame + 6, peer_mac) ||
      load_be16(frame + 12) != 0x0806U || load_be16(frame + 14) != 1U || load_be16(frame + 16) != 0x0800U ||
      frame[18] != 6U || frame[19] != 4U || load_be16(frame + 20) != 1U || !mac_equal(frame + 22, peer_mac) ||
      load_be32(frame + 28) != peer_ip || load_be32(frame + 38) != local_ip) return 0;
  return 1;
}
static uint32_t ref_reply(uint8_t *frame, uint32_t capacity, const uint8_t local_mac[6], const uint8_t peer_mac[6],
                          uint32_t local_ip, uint32_t peer_ip) {
  if (!frame || capacity < 42U || !local_mac || !peer_mac || !local_ip || !peer_ip) return 0;
  bytes_zero(frame, 42U);
  for (unsigned i = 0; i < 6; i++) { frame[i] = peer_mac[i]; frame[6 + i] = local_mac[i]; frame[22 + i] = local_mac[i]; frame[32 + i] = peer_mac[i]; }
  store_be16(frame + 12, 0x0806U); store_be16(frame + 14, 1U); store_be16(frame + 16, 0x0800U);
  frame[18] = 6U; frame[19] = 4U; store_be16(frame + 20, 2U);
  store_be32(frame + 28, local_ip); store_be32(frame + 38, peer_ip);
  return 42U;
}
/* kernel/rtl8125.c's wrappers over the object (built with AIUEOS_RTL8125_ARP_ONLY) */
#define req aiueos_rtl8125_direct_arp_request
#define rep aiueos_rtl8125_direct_arp_reply
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 41;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static unsigned n_cases, n_ok, n_bad, model_fail;
static uint8_t f1[2048], f2[2048], lm[6], pm[6];
static void cmp_req(uint32_t n, uint32_t li, uint32_t pi, unsigned tag) {
  int r1 = ref_request(f1, n, lm, pm, li, pi), r2 = req(f1, n, lm, pm, li, pi);
  n_cases++; if (r1) n_ok++;
  if (r1 != r2) { n_bad++; puts_("REQ-DIFF "); hex(n, 3); hex(tag, 4); hex(r1, 1); hex((uint32_t)r2, 2); putc_('\n'); }
}
static void cmp_rep(uint32_t cap, uint32_t li, uint32_t pi, unsigned tag) {
  for (int i = 0; i < 64; i++) f1[i] = f2[i] = (uint8_t)(0xa0 + i);
  uint32_t r1 = ref_reply(f1, cap, lm, pm, li, pi), r2 = rep(f2, cap, lm, pm, li, pi);
  int same = r1 == r2;
  for (int i = 0; i < 64; i++) if (f1[i] != f2[i]) same = 0;
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; puts_("REP-DIFF "); hex(cap, 3); hex(tag, 4); hex(r1, 2); hex(r2, 2); putc_('\n'); }
}
static void make_request(uint8_t *f, int dst, uint32_t li, uint32_t pi) {
  for (int i = 0; i < 6; i++) f[i] = dst == 0 ? 0xff : dst == 1 ? lm[i] : (uint8_t)rnd();
  for (int i = 0; i < 6; i++) { f[6 + i] = pm[i]; f[22 + i] = pm[i]; f[32 + i] = (uint8_t)rnd(); }
  store_be16(f + 12, 0x0806); store_be16(f + 14, 1); store_be16(f + 16, 0x0800); f[18] = 6; f[19] = 4; store_be16(f + 20, 1);
  store_be32(f + 28, pi); store_be32(f + 38, li);
}
void test_main(void) {
  static const uint32_t lens[] = {0, 1, 41, 42, 43, 60, 64, 1514, 2048};
  puts_("ARPDIFF\n");
  model_fail = (unsigned)rtl8125_handoff_model();
  if (model_fail) { puts_("MODEL-FAIL "); hex(model_fail, 4); putc_('\n'); } else puts_("AIUEOS_RTL8125_MODEL_OK arp=peer-bound-reply\n");
  for (unsigned k = 0; k < 400; k++) {
    for (int i = 0; i < 6; i++) { lm[i] = (uint8_t)rnd(); pm[i] = (uint8_t)rnd(); }
    if (k % 10 == 0) for (int i = 0; i < 6; i++) pm[i] = 0xff;
    uint32_t li = rnd() * 7u + 1u, pi = rnd() * 13u + 1u;
    if (k % 17 == 0) li = 0; if (k % 19 == 0) pi = 0; if (k % 23 == 0) li = 0xffffffffu;
    for (int i = 42; i < 2048; i++) f1[i] = (uint8_t)rnd();
    make_request(f1, (int)(k % 3), li, pi);
    for (unsigned L = 0; L < sizeof lens / 4; L++) cmp_req(lens[L], li, pi, k);
    /* every byte position of the 42, mutated by a random non-zero xor or set to the broadcast / zero byte */
    for (unsigned at = 0; at < 42; at++) {
      uint8_t save = f1[at];
      f1[at] ^= (uint8_t)(1 + rnd() % 255); cmp_req(42, li, pi, 0x1000 + at);
      f1[at] = (k & 1) ? 0xff : 0; cmp_req(42, li, pi, 0x2000 + at);
      f1[at] = save;
    }
    /* the source MAC equal to the local one, and the destination equal to the peer's */
    for (int i = 0; i < 6; i++) f1[6 + i] = lm[i]; cmp_req(42, li, pi, 0x3000 + k);
    for (int i = 0; i < 6; i++) { f1[6 + i] = pm[i]; f1[i] = pm[i]; } cmp_req(42, li, pi, 0x3100 + k);
    static const uint32_t caps[] = {0, 41, 42, 43, 64, 2048};
    for (unsigned c = 0; c < sizeof caps / 4; c++) cmp_rep(caps[c], li, pi, k);
  }
  /* refused by the object only: a MAC length other than 6, a null MAC, a length / address with a non-zero upper half */
  {
    unsigned bad = 0;
    for (int i = 0; i < 6; i++) { lm[i] = (uint8_t)rnd(); pm[i] = (uint8_t)rnd(); }
    make_request(f1, 0, 0x0a000002u, 0x0a000001u);
    if (!req(f1, 42, lm, pm, 0x0a000002u, 0x0a000001u)) bad++;
    if (kotoba_aiueos_rtl8125_arp_request(f1, 42, lm, 5, pm, 6, 0x0a000002u, 0x0a000001u)) bad++;
    if (kotoba_aiueos_rtl8125_arp_request(f1, 42, lm, 6, pm, 7, 0x0a000002u, 0x0a000001u)) bad++;
    if (kotoba_aiueos_rtl8125_arp_request(f1, 42, 0, 6, pm, 6, 0x0a000002u, 0x0a000001u)) bad++;
    if (kotoba_aiueos_rtl8125_arp_request(f1, 0x10000002aull, lm, 6, pm, 6, 0x0a000002u, 0x0a000001u)) bad++;
    if (kotoba_aiueos_rtl8125_arp_request(f1, 42, lm, 6, pm, 6, 0x10a000002ull, 0x0a000001u)) bad++;
    if (kotoba_aiueos_rtl8125_arp_request(f1, 16385, lm, 6, pm, 6, 0x0a000002u, 0x0a000001u)) bad++;
    for (int i = 0; i < 64; i++) f2[i] = 0x5a;
    if (kotoba_aiueos_rtl8125_arp_reply(f2, 64, lm, 6, pm, 5, 1, 2)) bad++;
    if (kotoba_aiueos_rtl8125_arp_reply(f2, 64, lm, 6, 0, 6, 1, 2)) bad++;
    if (kotoba_aiueos_rtl8125_arp_reply(f2, 64, lm, 6, pm, 6, 1, 0x100000002ull)) bad++;
    if (kotoba_aiueos_rtl8125_arp_reply(0, 64, lm, 6, pm, 6, 1, 2)) bad++;
    for (int i = 0; i < 64; i++) if (f2[i] != 0x5a) bad++;
    n_cases += 11; n_bad += bad;
    if (bad) { puts_("REFUSE-DIFF "); hex(bad, 2); putc_('\n'); }
  }
  puts_("CASES "); hex(n_cases, 5); puts_("ACCEPTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad + (model_fail ? 1 : 0), 5); putc_('\n'); puts_("DONE\n");
}
