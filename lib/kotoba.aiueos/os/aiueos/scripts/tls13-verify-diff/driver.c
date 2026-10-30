#include <stdint.h>
extern uint64_t kotoba_aiueos_sha256(const uint8_t *, uint64_t, uint8_t[32], uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_hmac(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *);
extern int64_t kotoba_aiueos_tls13_hkdf_expand_label(const uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_parse_ecdsa_der(const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_finished_ok(const uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_certverify(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t, uint8_t *, uint64_t);
static uint8_t ws[512];
/* the C's helpers as kernel/tls13.c had them (sha256 over the same object, hmac / expand-label over the key-schedule object) */
static uint16_t be16(const uint8_t *p) { return (uint16_t)(((uint32_t)p[0] << 8) | p[1]); }
static uint32_t be24(const uint8_t *p) { return ((uint32_t)p[0] << 16) | ((uint32_t)p[1] << 8) | p[2]; }
static void copy_bytes(uint8_t *d, const uint8_t *s, uint32_t n) { for (uint32_t i = 0; i < n; i++) d[i] = s[i]; }
static int sha256(const uint8_t *in, uint32_t n, uint8_t out[32]) { static const uint8_t empty[1] = {0}; return (int)kotoba_aiueos_sha256(n ? in : empty, n, out, ws, sizeof ws); }
static int hmac_sha256(const uint8_t *k, uint32_t kl, const uint8_t *d, uint32_t dl, uint8_t out[32]) { return kotoba_aiueos_tls13_hmac(k, kl, d, dl, out) == 1; }
static int hkdf_expand_label(const uint8_t *s, const char *label, const uint8_t *c, uint32_t cl, uint8_t *o, uint32_t ol) {
  uint32_t i = 0; while (label[i]) i++; return kotoba_aiueos_tls13_hkdf_expand_label(s, 32, (const uint8_t *)label, i, c, cl, o, ol) == 1; }
static int parse_ecdsa_der(const uint8_t *p, uint32_t n, uint8_t rs[64]) { return kotoba_aiueos_tls13_parse_ecdsa_der(p, n, rs, 64) == 1; }
/* finish_check, with its globals as parameters */
static int ref_finished(const uint8_t *s_hs_secret, const uint8_t *transcript, uint32_t transcript_len, const uint8_t *verify, uint32_t n) {
  uint8_t finished_key[32], th[32], expect[32];
  uint32_t i, diff = 0;
  if (n != 32) return 0;
  if (!hkdf_expand_label(s_hs_secret, "finished", 0, 0, finished_key, 32)) return 0;
  if (!sha256(transcript, transcript_len, th)) return 0;
  if (!hmac_sha256(finished_key, 32, th, 32, expect)) return 0;
  for (i = 0; i < 32; i++) diff |= (uint32_t)(verify[i] ^ expect[i]);
  return diff == 0;
}
/* verify_certificate_verify, with its globals as parameters; *scheme_out is what certverify_scheme would hold (-1: not set) */
static int ref_certverify(const uint8_t *hs, uint32_t n, const uint8_t *transcript, uint32_t transcript_len,
                          uint8_t *cv_rs, uint8_t *cv_digest, int32_t *scheme_out) {
  uint32_t mlen, siglen, i;
  uint8_t th[32], digest[32], rs[64], content[130];
  static const uint8_t ctx[33] = {'T','L','S',' ','1','.','3',',',' ','s','e','r','v','e','r',' ',
    'C','e','r','t','i','f','i','c','a','t','e','V','e','r','i','f','y'};
  uint16_t certverify_scheme;
  if (n < 8 || hs[0] != 0x0f) return 0;
  mlen = be24(hs + 1);
  if (mlen + 4 != n) return 0;
  certverify_scheme = be16(hs + 4); *scheme_out = certverify_scheme;
  if (certverify_scheme != 0x0403) return 0;
  siglen = be16(hs + 6);
  if (8 + siglen != n) return 0;
  if (!parse_ecdsa_der(hs + 8, siglen, rs)) return 0;
  if (!sha256(transcript, transcript_len, th)) return 0;
  for (i = 0; i < 64; i++) content[i] = 0x20;
  copy_bytes(content + 64, ctx, 33);
  content[97] = 0;
  copy_bytes(content + 98, th, 32);
  if (!sha256(content, 130, digest)) return 0;
  copy_bytes(cv_rs, rs, 64);
  copy_bytes(cv_digest, digest, 32);
  return 1;
}
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 13;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static uint8_t secret[32], tr[12288], verify[33], hs[300], rs1[64], rs2[64], dg1[32], dg2[32], key[32];
static unsigned n_cases, n_ok, n_bad;
static void fin_case(uint32_t tl, uint32_t vl, unsigned tag) {
  int r1 = ref_finished(secret, tr, tl, verify, vl);
  int r2 = (int)kotoba_aiueos_tls13_finished_ok(secret, 32, tr, tl, verify, vl);
  n_cases++; if (r1) n_ok++;
  if ((r1 != 0) != (r2 != 0)) { n_bad++; puts_("FIN-DIFF "); hex(tl, 4); hex(vl, 2); hex(tag, 3); hex(r1, 1); hex(r2, 1); putc_('\n'); }
}
static uint32_t der_int(uint8_t *p, uint32_t len) { p[0] = 2; p[1] = (uint8_t)len; for (uint32_t i = 0; i < len; i++) p[2 + i] = (uint8_t)rnd(); if (len) p[2] = 0x40 | (rnd() & 0x3f); return 2 + len; }
static uint32_t make_cv(uint8_t *p) {
  uint32_t a = der_int(p + 10, 32), b2 = der_int(p + 10 + a, 32);
  uint32_t sig = 2 + a + b2;
  p[8] = 0x30; p[9] = (uint8_t)(a + b2);
  p[0] = 0x0f; p[1] = 0; p[2] = (uint8_t)((4 + sig) >> 8); p[3] = (uint8_t)(4 + sig);
  p[4] = 0x04; p[5] = 0x03; p[6] = (uint8_t)(sig >> 8); p[7] = (uint8_t)sig;
  return 8 + sig;
}
static void cv_case(uint32_t n, uint32_t tl, unsigned tag) {
  int32_t sch = -1;
  for (int i = 0; i < 64; i++) rs1[i] = rs2[i] = 0x77;
  for (int i = 0; i < 32; i++) dg1[i] = dg2[i] = 0x66;
  int r1 = ref_certverify(hs, n, tr, tl, rs1, dg1, &sch);
  int64_t r2 = kotoba_aiueos_tls13_certverify(hs, n, tr, tl, rs2, 64, dg2, 32);
  int same = (r1 != 0) == ((r2 & 1) != 0) && (sch < 0 ? r2 == 0 : (r2 >> 1) == sch);
  if (r1) { for (int i = 0; i < 64; i++) if (rs1[i] != rs2[i]) same = 0; for (int i = 0; i < 32; i++) if (dg1[i] != dg2[i]) same = 0; }
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; puts_("CV-DIFF "); hex(n, 3); hex(tl, 4); hex(tag, 4); hex(r1, 1); hex((uint64_t)r2, 5); hex((uint32_t)sch, 4); putc_('\n'); }
}
void test_main(void) {
  static const uint32_t tls[] = {0, 1, 63, 64, 1000, 4096, 12224};
  puts_("VERIFYDIFF\n");
  for (int i = 0; i < 12288; i++) tr[i] = (uint8_t)rnd();
  for (unsigned t = 0; t < sizeof tls / 4; t++)
    for (unsigned k = 0; k < 12; k++) {
      for (int i = 0; i < 32; i++) secret[i] = (uint8_t)rnd();
      /* the right verify data: what the C computes for this secret and transcript */
      { uint8_t fk[32], th[32]; hkdf_expand_label(secret, "finished", 0, 0, fk, 32); sha256(tr, tls[t], th); hmac_sha256(fk, 32, th, 32, verify); }
      fin_case(tls[t], 32, 0);
      fin_case(tls[t], 31, 1); fin_case(tls[t], 33, 2);
      uint8_t s = verify[k % 32]; verify[k % 32] ^= (uint8_t)(1 << (k % 8)); fin_case(tls[t], 32, 3 + k); verify[k % 32] = s;
    }
  for (unsigned k = 0; k < 1500; k++) {
    uint32_t n = make_cv(hs), tl = tls[k % 7];
    unsigned m = k % 6;
    if (m == 1) hs[rnd() % n] = (uint8_t)rnd();
    if (m == 2) { hs[4] = (uint8_t)rnd(); hs[5] = (uint8_t)rnd(); }
    if (m == 3) hs[0] = (uint8_t)rnd();
    if (m == 4) n = rnd() % (n + 3);
    if (m == 5) hs[6 + (rnd() & 1)] ^= (uint8_t)(1 + (rnd() & 7));
    cv_case(n, tl, k);
  }
  puts_("CASES "); hex(n_cases, 5); puts_("ACCEPTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
