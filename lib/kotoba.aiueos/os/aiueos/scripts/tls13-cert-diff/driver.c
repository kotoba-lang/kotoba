#include <stdint.h>
extern int64_t kotoba_aiueos_tls13_find_p256_point(const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_parse_ecdsa_der(const uint8_t *, uint64_t, uint8_t *, uint64_t);
static void copy_bytes(uint8_t *d, const uint8_t *s, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; i++) d[i] = s[i];
}

static void zero_bytes(uint8_t *d, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; i++) d[i] = 0;
}

static const uint8_t p256_spki_prefix[27] = {
  0x30,0x59,0x30,0x13,0x06,0x07,0x2a,0x86,0x48,0xce,0x3d,0x02,0x01,
  0x06,0x08,0x2a,0x86,0x48,0xce,0x3d,0x03,0x01,0x07,0x03,0x42,0x00,0x04};

static int find_p256_point(const uint8_t *p, uint32_t n, uint8_t out[64]) {
  uint32_t i, j, hit;
  if (n < 27 + 64) return 0;
  for (i = 0; i + 27 + 64 <= n; i++) {
    hit = 1;
    for (j = 0; j < 27; j++) {
      if (p[i + j] != p256_spki_prefix[j]) { hit = 0; break; }
    }
    if (hit) {
      copy_bytes(out, p + i + 27, 64);
      return 1;
    }
  }
  return 0;
}

static int der_int_be32(const uint8_t *p, uint32_t n, uint32_t *used, uint8_t out[32]) {
  uint32_t len, off, skip;
  if (n < 2 || p[0] != 0x02) return 0;
  len = p[1];
  off = 2;
  if ((len & 0x80) != 0 || len == 0 || off + len > n) return 0;
  skip = 0;
  while (skip + 1 < len && p[off + skip] == 0) skip++;
  if (len - skip > 32) return 0;
  zero_bytes(out, 32);
  copy_bytes(out + (32 - (len - skip)), p + off + skip, len - skip);
  *used = off + len;
  return 1;
}

static int parse_ecdsa_der(const uint8_t *p, uint32_t n, uint8_t rs[64]) {
  uint32_t used = 0, inner;
  if (n < 8 || p[0] != 0x30) return 0;
  if ((p[1] & 0x80) != 0 || 2u + p[1] != n) return 0;
  if (!der_int_be32(p + 2, n - 2, &used, rs)) return 0;
  inner = 2 + used;
  if (!der_int_be32(p + inner, n - inner, &used, rs + 32)) return 0;
  return inner + used == n;
}

static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 11;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static uint8_t buf[12288], o1[64], o2[64];
static unsigned n_cases, n_bad, n_ok;
static void check(const char *what, int r1, int r2, uint32_t a, uint32_t b) {
  n_cases++; if (r1) n_ok++;
  int same = (r1 != 0) == (r2 != 0);
  for (int i = 0; i < 64; i++) if (o1[i] != o2[i]) same = 0;
  if (!same) { n_bad++; puts_(what); hex(a, 4); hex(b, 4); hex(r1, 1); hex(r2, 1); putc_('\n'); }
}
static void find_case(uint32_t n) {
  for (int i = 0; i < 64; i++) o1[i] = o2[i] = 0x77;
  check("FIND-DIFF ", find_p256_point(buf, n, o1), (int)kotoba_aiueos_tls13_find_p256_point(buf, n, o2, 64), n, 0);
}
static uint32_t der_int(uint8_t *p, uint32_t len, int zeros, int top) {
  /* tag, length, then `zeros` leading 0x00 and the rest random (first non-zero byte `top` if >= 0) */
  p[0] = 2; p[1] = (uint8_t)len;
  for (uint32_t i = 0; i < len; i++) p[2 + i] = (uint8_t)rnd();
  for (int i = 0; i < zeros && (uint32_t)i < len; i++) p[2 + i] = 0;
  if (top >= 0 && (uint32_t)zeros < len) p[2 + zeros] = (uint8_t)top;
  return 2 + len;
}
static uint32_t make_sig(uint8_t *p, uint32_t rl, int rz, uint32_t sl, int sz) {
  uint32_t a = der_int(p + 2, rl, rz, 0x80 | (rnd() & 0x7f));
  uint32_t b = der_int(p + 2 + a, sl, sz, (int)(rnd() & 0xff));
  p[0] = 0x30; p[1] = (uint8_t)(a + b);
  return 2 + a + b;
}
static void parse_case(uint32_t n, uint32_t tag) {
  for (int i = 0; i < 64; i++) o1[i] = o2[i] = 0x77;
  check("DER-DIFF ", parse_ecdsa_der(buf, n, o1), (int)kotoba_aiueos_tls13_parse_ecdsa_der(buf, n, o2, 64), n, tag);
}
void test_main(void) {
  static const uint32_t ns[] = {0, 90, 91, 92, 150, 300, 4096, 12288};
  puts_("CERTDIFF\n");
  for (unsigned a = 0; a < sizeof ns / 4; a++) {
    uint32_t n = ns[a];
    for (uint32_t i = 0; i < n; i++) buf[i] = (uint8_t)rnd();
    find_case(n);                                      /* no prefix */
    if (n >= 91) {
      static const int64_t at[] = {0, 1, -91, -90, 17};
      for (unsigned k = 0; k < 5; k++) {
        for (uint32_t i = 0; i < n; i++) buf[i] = (uint8_t)rnd();
        int64_t o = at[k] < 0 ? (int64_t)n + at[k] : at[k];
        if (o < 0 || o + 27 > (int64_t)n) continue;
        for (int j = 0; j < 27; j++) buf[o + j] = p256_spki_prefix[j];
        find_case(n);
        if (o + 27 + 91 <= (int64_t)n) { for (int j = 0; j < 27; j++) buf[o + 64 + 27 + j] = p256_spki_prefix[j]; find_case(n); }
        for (int j = 0; j < 27; j++) { uint8_t s = buf[o + j]; buf[o + j] ^= 1; find_case(n); buf[o + j] = s; }
      }
    }
  }
  /* structured signatures: r and s lengths 1..34, leading zeros 0..2 */
  for (uint32_t rl = 1; rl <= 34; rl++)
    for (uint32_t sl = 1; sl <= 34; sl += 3)
      for (int z = 0; z < 3; z++) {
        uint32_t n = make_sig(buf, rl, z, sl, z == 2 ? 1 : 0);
        parse_case(n, rl * 100 + sl);
        parse_case(n + 1, 1);                 /* trailing byte */
        parse_case(n - 1, 2);                 /* truncated */
      }
  /* fuzz: valid 70..72-byte signatures with one, two or three random byte flips, and random lengths */
  for (unsigned k = 0; k < 4000; k++) {
    uint32_t n = make_sig(buf, 32 + (rnd() & 1), 0, 32 + (rnd() & 1), 0);
    unsigned flips = 1 + rnd() % 3;
    for (unsigned f = 0; f < flips; f++) buf[rnd() % n] = (uint8_t)rnd();
    uint32_t m = (rnd() % 8 == 0) ? (rnd() % 80) : n;
    parse_case(m, k);
  }
  puts_("CASES "); hex(n_cases, 5); puts_("ACCEPTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
