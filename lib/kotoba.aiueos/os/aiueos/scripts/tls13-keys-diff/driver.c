#include <stdint.h>
extern uint64_t kotoba_aiueos_sha256(const uint8_t *, uint64_t, uint8_t[32], uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_hmac(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *);
extern int64_t kotoba_aiueos_tls13_hkdf_expand_label(const uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_hs_keys(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_ap_keys(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_finished_mac(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
static uint8_t ws[512];
/* the C's helpers as kernel/tls13.c has them (sha256 over the same object, hmac / expand-label over the key-schedule object) */
static void copy_bytes(uint8_t *d, const uint8_t *s, uint32_t n) { for (uint32_t i = 0; i < n; i++) d[i] = s[i]; }
static void zero_bytes(uint8_t *d, uint32_t n) { for (uint32_t i = 0; i < n; i++) d[i] = 0; }
static int sha256(const uint8_t *in, uint32_t n, uint8_t out[32]) { static const uint8_t empty[1] = {0}; return (int)kotoba_aiueos_sha256(n ? in : empty, n, out, ws, sizeof ws); }
static int hmac_sha256(const uint8_t *k, uint32_t kl, const uint8_t *d, uint32_t dl, uint8_t out[32]) { return kotoba_aiueos_tls13_hmac(k, kl, d, dl, out) == 1; }
static int hkdf_extract(const uint8_t *salt, uint32_t salt_len, const uint8_t *ikm, uint32_t ikm_len, uint8_t out[32]) {
  static const uint8_t zeros[32] = {0}; if (!salt || salt_len == 0) { salt = zeros; salt_len = 32; } return hmac_sha256(salt, salt_len, ikm, ikm_len, out); }
static int hkdf_expand_label(const uint8_t *s, const char *label, const uint8_t *c, uint32_t cl, uint8_t *o, uint32_t ol) {
  uint32_t i = 0; while (label[i]) i++; return kotoba_aiueos_tls13_hkdf_expand_label(s, 32, (const uint8_t *)label, i, c, cl, o, ol) == 1; }
static int derive_secret(const uint8_t *secret, const char *label, const uint8_t *msgs, uint32_t msgs_len, uint8_t out[32]) {
  uint8_t th[32]; if (!sha256(msgs, msgs_len, th)) return 0; return hkdf_expand_label(secret, label, th, 32, out, 32); }
/* derive_hs_keys after the X25519, with its globals as one output: hs secret | c hs | s hs | c key | c iv | s key | s iv */
static int ref_hs(const uint8_t *shared, const uint8_t *transcript, uint32_t transcript_len, uint8_t *o) {
  uint8_t early[32], derived[32], empty_ikm[32], c_hs[32], s_hs[32];
  uint8_t *handshake_secret = o, *c_hs_key = o + 96, *c_hs_iv = o + 112, *s_hs_key = o + 124, *s_hs_iv = o + 140;
  zero_bytes(empty_ikm, 32);
  if (!hkdf_extract(0, 0, empty_ikm, 32, early)) return 0;
  if (!derive_secret(early, "derived", 0, 0, derived)) return 0;
  if (!hkdf_extract(derived, 32, shared, 32, handshake_secret)) return 0;
  if (!derive_secret(handshake_secret, "c hs traffic", transcript, transcript_len, c_hs)) return 0;
  if (!derive_secret(handshake_secret, "s hs traffic", transcript, transcript_len, s_hs)) return 0;
  if (!hkdf_expand_label(c_hs, "key", 0, 0, c_hs_key, 16)) return 0;
  if (!hkdf_expand_label(c_hs, "iv", 0, 0, c_hs_iv, 12)) return 0;
  if (!hkdf_expand_label(s_hs, "key", 0, 0, s_hs_key, 16)) return 0;
  if (!hkdf_expand_label(s_hs, "iv", 0, 0, s_hs_iv, 12)) return 0;
  copy_bytes(o + 32, c_hs, 32); copy_bytes(o + 64, s_hs, 32);
  return 1;
}
/* derive_ap_keys: c key | c iv | s key | s iv */
static int ref_ap(const uint8_t *handshake_secret, const uint8_t *transcript, uint32_t transcript_len, uint8_t *o) {
  uint8_t derived[32], master[32], zeros[32], c_ap[32], s_ap[32];
  zero_bytes(zeros, 32);
  if (!derive_secret(handshake_secret, "derived", 0, 0, derived)) return 0;
  if (!hkdf_extract(derived, 32, zeros, 32, master)) return 0;
  if (!derive_secret(master, "c ap traffic", transcript, transcript_len, c_ap)) return 0;
  if (!derive_secret(master, "s ap traffic", transcript, transcript_len, s_ap)) return 0;
  if (!hkdf_expand_label(c_ap, "key", 0, 0, o, 16)) return 0;
  if (!hkdf_expand_label(c_ap, "iv", 0, 0, o + 16, 12)) return 0;
  if (!hkdf_expand_label(s_ap, "key", 0, 0, o + 28, 16)) return 0;
  if (!hkdf_expand_label(s_ap, "iv", 0, 0, o + 44, 12)) return 0;
  return 1;
}
/* aiueos_tls13_take_finished's verify data */
static int ref_fin(const uint8_t *c_hs_secret, const uint8_t *transcript, uint32_t transcript_len, uint8_t *verify) {
  uint8_t finished_key[32], th[32];
  if (!hkdf_expand_label(c_hs_secret, "finished", 0, 0, finished_key, 32)) return 0;
  if (!sha256(transcript, transcript_len, th)) return 0;
  if (!hmac_sha256(finished_key, 32, th, 32, verify)) return 0;
  return 1;
}
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 29;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static uint8_t secret[32], tr[12288], o1[160], o2[160];
static unsigned n_cases, n_ok, n_bad;
static void check(int r1, int64_t r2, uint32_t len, char kind, uint32_t tl, unsigned tag) {
  int same = (r1 != 0) == (r2 != 0) && (r2 == 0 || r2 == 1);
  if (r1) for (uint32_t i = 0; i < 160; i++) if (o1[i] != o2[i] && i < len) same = 0;
  for (uint32_t i = len; i < 160; i++) if (o2[i] != 0x5a) same = 0;   /* nothing past the output is written */
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; puts_("DIFF "); putc_(kind); putc_(' '); hex(tl, 4); hex(tag, 3); hex(r1, 1); hex((uint64_t)r2, 2); putc_('\n'); }
}
static void pre(void) { for (int i = 0; i < 160; i++) o1[i] = 0xa5, o2[i] = 0x5a; }
void test_main(void) {
  static const uint32_t tls[] = {0, 1, 55, 56, 63, 64, 65, 119, 1000, 4096, 12224, 12288};
  puts_("KEYSDIFF\n");
  for (int i = 0; i < 12288; i++) tr[i] = (uint8_t)rnd();
  for (unsigned t = 0; t < sizeof tls / 4; t++)
    for (unsigned k = 0; k < 24; k++) {
      for (int i = 0; i < 32; i++) secret[i] = (uint8_t)rnd();
      if (k == 0) zero_bytes(secret, 32);
      if (k == 1) for (int i = 0; i < 32; i++) secret[i] = 0xff;
      pre(); check(ref_hs(secret, tr, tls[t], o1), kotoba_aiueos_tls13_hs_keys(secret, 32, tr, tls[t], o2, 152), 152, 'H', tls[t], k);
      pre(); check(ref_ap(secret, tr, tls[t], o1), kotoba_aiueos_tls13_ap_keys(secret, 32, tr, tls[t], o2, 56), 56, 'A', tls[t], k);
      pre(); check(ref_fin(secret, tr, tls[t], o1), kotoba_aiueos_tls13_finished_mac(secret, 32, tr, tls[t], o2, 32), 32, 'F', tls[t], k);
    }
  /* refused arguments: a wrong secret length, a short output, a length with a non-zero upper half -- nothing is written */
  {
    static const uint64_t bad_sn[] = {0, 31, 33, 0x100000020ull}, bad_tl[] = {0x100000000ull, 0x100000040ull};
    for (unsigned i = 0; i < 4; i++) {
      pre(); check(0, kotoba_aiueos_tls13_hs_keys(secret, bad_sn[i], tr, 64, o2, 152), 0, 'h', i, 0);
      pre(); check(0, kotoba_aiueos_tls13_ap_keys(secret, bad_sn[i], tr, 64, o2, 56), 0, 'a', i, 0);
      pre(); check(0, kotoba_aiueos_tls13_finished_mac(secret, bad_sn[i], tr, 64, o2, 32), 0, 'f', i, 0);
    }
    for (unsigned i = 0; i < 2; i++) {
      pre(); check(0, kotoba_aiueos_tls13_hs_keys(secret, 32, tr, bad_tl[i], o2, 152), 0, 'h', i, 1);
      pre(); check(0, kotoba_aiueos_tls13_ap_keys(secret, 32, tr, bad_tl[i], o2, 56), 0, 'a', i, 1);
      pre(); check(0, kotoba_aiueos_tls13_finished_mac(secret, 32, tr, bad_tl[i], o2, 32), 0, 'f', i, 1);
    }
    pre(); check(0, kotoba_aiueos_tls13_hs_keys(secret, 32, tr, 64, o2, 151), 0, 'h', 0, 2);
    pre(); check(0, kotoba_aiueos_tls13_ap_keys(secret, 32, tr, 64, o2, 55), 0, 'a', 0, 2);
    pre(); check(0, kotoba_aiueos_tls13_finished_mac(secret, 32, tr, 64, o2, 31), 0, 'f', 0, 2);
    pre(); check(0, kotoba_aiueos_tls13_hs_keys(secret, 32, tr, 64, o2, 0x100000098ull), 0, 'h', 0, 3);
  }
  puts_("CASES "); hex(n_cases, 5); puts_("ACCEPTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
