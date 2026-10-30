#include <stdint.h>
int old_method_is(const uint8_t *, uint32_t, const char *); int new_method_is(const uint8_t *, uint32_t, const char *);
int old_publickey_fields(const uint8_t *, uint32_t, int *, const uint8_t **, uint32_t *, const uint8_t **, uint32_t *, uint32_t *);
int new_publickey_fields(const uint8_t *, uint32_t, int *, const uint8_t **, uint32_t *, const uint8_t **, uint32_t *, uint32_t *);
int old_authorized_blob(const uint8_t *, uint32_t, uint8_t[64]); int new_authorized_blob(const uint8_t *, uint32_t, uint8_t[64]);
static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t seed = 89;
static uint64_t rnd(void) { seed = seed * 6364136223846793005ull + 1442695040888963407ull; return seed >> 9; }
static const uint8_t AX[32] = {0x46,0x87,0x0e,0x7c,0xe7,0x9b,0xcb,0xc6,0x01,0x47,0x14,0x61,0x8f,0x35,0x43,0xdc,
  0x1e,0x6d,0x67,0xcb,0xc5,0xda,0x37,0x8d,0x91,0xc8,0xd7,0x17,0x11,0xaf,0x1a,0xbf};
static const uint8_t AY[32] = {0x04,0xae,0xd0,0x99,0x59,0x46,0xfb,0x24,0x4e,0x15,0x10,0x9e,0xe2,0x76,0xc5,0x79,
  0xfa,0x0b,0x14,0x40,0x5b,0xf9,0x50,0x75,0x22,0xee,0xe2,0x65,0x68,0xd2,0xc0,0xf3};
static uint8_t p[1100], blob[200];
static uint32_t at, bl;
static unsigned n_cases, n_ok, n_bad;
static void str(uint8_t *buf, uint32_t *pos, const char *s) {
  uint32_t n = 0; while (s[n]) n++;
  buf[*pos] = (uint8_t)(n >> 24); buf[*pos + 1] = (uint8_t)(n >> 16); buf[*pos + 2] = (uint8_t)(n >> 8); buf[*pos + 3] = (uint8_t)n;
  for (uint32_t i = 0; i < n; i++) buf[*pos + 4 + i] = (uint8_t)s[i];
  *pos += 4 + n;
}
static void bytes(uint8_t *buf, uint32_t *pos, const uint8_t *b, uint32_t n) {
  buf[*pos] = (uint8_t)(n >> 24); buf[*pos + 1] = (uint8_t)(n >> 16); buf[*pos + 2] = (uint8_t)(n >> 8); buf[*pos + 3] = (uint8_t)n;
  for (uint32_t i = 0; i < n; i++) buf[*pos + 4 + i] = b[i];
  *pos += 4 + n;
}
static void make_blob(int authorized, unsigned k) {
  uint8_t pt[65]; pt[0] = 4;
  for (int i = 0; i < 32; i++) { pt[1 + i] = authorized ? AX[i] : (uint8_t)rnd(); pt[33 + i] = authorized ? AY[i] : (uint8_t)rnd(); }
  if (authorized && k % 5 == 1) pt[33 + (rnd() % 32)] ^= 1;          /* one Y byte off */
  if (authorized && k % 5 == 2) pt[1 + (rnd() % 32)] ^= 0x80;        /* one X byte off */
  bl = 0;
  str(blob, &bl, k % 23 == 3 ? "ecdsa-sha2-nistp384" : "ecdsa-sha2-nistp256");
  str(blob, &bl, k % 19 == 4 ? "nistp384" : "nistp256");
  bytes(blob, &bl, pt, k % 17 == 5 ? 64 : 65);
}
static void make_request(unsigned k) {
  at = 0; p[at++] = (uint8_t)(k % 31 == 0 ? 51 : 50);
  str(p, &at, k % 13 == 1 ? "Runtime" : "runtime");
  str(p, &at, k % 11 == 2 ? "ssh-userauth" : "ssh-connection");
  str(p, &at, k % 4 == 0 ? "none" : (k % 29 == 7 ? "password" : "publickey"));
  if (k % 4 != 0) {
    p[at++] = (uint8_t)(k % 3 == 0 ? 0 : 1);
    str(p, &at, k % 7 == 3 ? "ssh-ed25519" : "ecdsa-sha2-nistp256");
    make_blob(k % 2 == 0, k);
    bytes(p, &at, blob, bl);
    if (k % 3 != 0) { uint8_t sig[20]; for (int i = 0; i < 20; i++) sig[i] = (uint8_t)rnd(); bytes(p, &at, sig, 20); }
  }
}
static void compare(uint32_t n, unsigned tag) {
  int same = 1;
  same &= old_method_is(p, n, "none") == new_method_is(p, n, "none");
  same &= old_method_is(p, n, "publickey") == new_method_is(p, n, "publickey");
  int hs1 = -1, hs2 = -1; const uint8_t *a1 = 0, *a2 = 0, *b1 = 0, *b2 = 0; uint32_t al1 = 7, al2 = 7, bl1 = 7, bl2 = 7, k1 = 9, k2 = 9;
  int r1 = old_publickey_fields(p, n, &hs1, &a1, &al1, &b1, &bl1, &k1), r2 = new_publickey_fields(p, n, &hs2, &a2, &al2, &b2, &bl2, &k2);
  same &= r1 == r2;
  if (r1 && r2) same &= hs1 == hs2 && a1 == a2 && al1 == al2 && b1 == b2 && bl1 == bl2 && k1 == k2;
  if (r1) {
    uint8_t q1[64], q2[64]; for (int i = 0; i < 64; i++) q1[i] = q2[i] = 0x5a;
    int s1 = old_authorized_blob(b1, bl1, q1), s2 = new_authorized_blob(b1, bl1, q2);
    same &= s1 == s2; for (int i = 0; i < 64; i++) if (q1[i] != q2[i]) same = 0;
    if (s1) n_ok++;
  }
  n_cases++;
  if (!same) { n_bad++; if (n_bad < 8) { puts_("SSH-DIFF "); hex(tag, 5); hex(n, 3); hex(r1, 1); hex(r2, 1); putc_('\n'); } }
}
void test_main(void) {
  puts_("SSHUSERAUTHDIFF\n");
  for (unsigned k = 0; k < 600; k++) {
    make_request(k); uint32_t n = at;
    compare(n, k * 10);
    for (uint32_t cut = 0; cut < 6; cut++) if (n > cut) compare(n - 1 - (uint32_t)(rnd() % (n - cut)), k * 10 + 1);   /* truncated */
    if (k % 6 == 0) for (uint32_t i = 0; i < n; i++) { uint8_t s = p[i]; p[i] ^= (uint8_t)(1 + rnd() % 255); compare(n, k * 10 + 2); p[i] = s; }
    for (uint32_t i = 1; i + 4 <= n; i += 1 + (uint32_t)(rnd() % 40)) { uint8_t s = p[i + 3]; p[i + 3] = (uint8_t)(s + 1); compare(n, k * 10 + 3); p[i + 3] = (uint8_t)(s - 1); compare(n, k * 10 + 4); p[i + 3] = s; }
  }
  /* the blob check alone over blobs that are not inside a request */
  for (unsigned k = 0; k < 400; k++) {
    make_blob(1, k);
    uint8_t q1[64], q2[64]; for (int i = 0; i < 64; i++) q1[i] = q2[i] = 0x5a;
    uint32_t n = k % 9 == 0 ? bl - 1 - (uint32_t)(rnd() % 3) : bl;
    int s1 = old_authorized_blob(blob, n, q1), s2 = new_authorized_blob(blob, n, q2);
    int same = s1 == s2; for (int i = 0; i < 64; i++) if (q1[i] != q2[i]) same = 0;
    n_cases++; if (s1) n_ok++; if (!same) { n_bad++; if (n_bad < 8) { puts_("BLOB-DIFF "); hex(k, 3); hex(s1, 1); hex(s2, 1); putc_('\n'); } }
  }
  puts_("CASES "); hex(n_cases, 5); puts_("AUTHORIZED "); hex(n_ok, 4); puts_("DIFFS "); hex(n_bad, 4); putc_('\n'); puts_("DONE\n");
}
