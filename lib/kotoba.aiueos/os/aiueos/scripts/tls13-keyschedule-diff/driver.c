#include <stdint.h>
extern uint64_t kotoba_aiueos_sha256(const uint8_t *, uint64_t, uint8_t[32], uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_hmac(const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *);
extern int64_t kotoba_aiueos_tls13_hkdf_expand_label(const uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
static uint8_t ref_ws[512], ref_block[64 + 12288];
static void copy_bytes(uint8_t *d, const uint8_t *s, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; i++) d[i] = s[i];
}

static void put16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v;
}

static int ref_sha256(const uint8_t *in, uint32_t n, uint8_t out[32]) {
  static const uint8_t empty[1] = {0};
  const uint8_t *p = (n == 0) ? empty : in;
  return (int)kotoba_aiueos_sha256(p, n, out, ref_ws, sizeof(ref_ws));
}

static int ref_hmac(const uint8_t *key, uint32_t key_len,
                       const uint8_t *data, uint32_t data_len, uint8_t out[32]) {
  uint8_t ipad[64], opad[64], inner[32];
  uint32_t i;
  uint8_t kh[32];
  const uint8_t *k = key;
  uint32_t klen = key_len;
  if (64 + data_len > 12288) return 0;
  if (klen > 64) {
    if (!ref_sha256(key, klen, kh)) return 0;
    k = kh;
    klen = 32;
  }
  for (i = 0; i < 64; i++) {
    uint8_t b = (i < klen) ? k[i] : 0;
    ipad[i] = (uint8_t)(b ^ 0x36);
    opad[i] = (uint8_t)(b ^ 0x5c);
  }
  copy_bytes(ref_block, ipad, 64);
  copy_bytes(ref_block + 64, data, data_len);
  if (!ref_sha256(ref_block, 64 + data_len, inner)) return 0;
  copy_bytes(ref_block, opad, 64);
  copy_bytes(ref_block + 64, inner, 32);
  return ref_sha256(ref_block, 96, out);
}

static int ref_expand(const uint8_t *secret, const char *label,
                             const uint8_t *ctx, uint32_t ctx_len,
                             uint8_t *out, uint32_t out_len) {
  uint8_t info[256], full[32];
  uint32_t labellen = 0;
  uint32_t i, infolen;
  const char *prefix = "tls13 ";
  while (prefix[labellen]) labellen++;
  i = 0;
  while (label[i]) i++;
  if (6 + i + ctx_len + 4 > sizeof(info) || out_len > 32) return 0;
  put16(info, (uint16_t)out_len);
  info[2] = (uint8_t)(6 + i);
  copy_bytes(info + 3, (const uint8_t *)prefix, 6);
  copy_bytes(info + 9, (const uint8_t *)label, i);
  info[9 + i] = (uint8_t)ctx_len;
  if (ctx_len) copy_bytes(info + 10 + i, ctx, ctx_len);
  infolen = 10 + i + ctx_len;
  info[infolen] = 0x01;
  if (!ref_hmac(secret, 32, info, infolen + 1, full)) return 0;
  copy_bytes(out, full, out_len);
  return 1;
}

static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint64_t fnv(const uint8_t *p, uint32_t n) { uint64_t h = 1469598103934665603ull; for (uint32_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; } return h; }
static uint32_t seed = 7;
static uint8_t rnd(void) { seed = seed * 1103515245u + 12345u; return (uint8_t)(seed >> 16); }
static uint8_t key[256], data[12288], ctx[256], o1[32], o2[32];
static char label[256];
static int same(const uint8_t *a, const uint8_t *b) { for (int i = 0; i < 32; i++) if (a[i] != b[i]) return 0; return 1; }
void test_main(void) {
  static const uint32_t kl[] = {0, 1, 20, 32, 63, 64, 65, 100, 200};
  static const uint32_t dl[] = {0, 1, 8, 55, 56, 64, 300, 4096, 12224, 12225};
  unsigned bad = 0, n = 0;
  puts_("KSDIFF\n");
  /* RFC 4231 test case 1: key 0x0b x 20, data "Hi There" */
  for (int i = 0; i < 20; i++) key[i] = 0x0b;
  const char *hi = "Hi There"; for (int i = 0; i < 8; i++) data[i] = (uint8_t)hi[i];
  hex((uint64_t)kotoba_aiueos_tls13_hmac(key, 20, data, 8, o2), 2); hex(fnv(o2, 32), 16); hex(o2[0], 2); hex(o2[31], 2); putc_('\n');
  for (unsigned a = 0; a < sizeof kl / 4; a++)
    for (unsigned b = 0; b < sizeof dl / 4; b++) {
      for (uint32_t i = 0; i < kl[a]; i++) key[i] = rnd();
      for (uint32_t i = 0; i < dl[b]; i++) data[i] = rnd();
      for (int i = 0; i < 32; i++) o1[i] = o2[i] = 0x77;
      int r1 = ref_hmac(key, kl[a], data, dl[b], o1);
      int r2 = (int)kotoba_aiueos_tls13_hmac(key, kl[a], data, dl[b], o2);
      n++; if ((r1 != 0) != (r2 != 0) || !same(o1, o2)) { bad++; puts_("HMAC-DIFF "); hex(kl[a], 3); hex(dl[b], 4); putc_('\n'); }
      hex(r2 != 0, 1); hex(fnv(o2, 32), 16); if ((a * 10 + b) % 4 == 3) putc_('\n');
    }
  putc_('\n');
  static const uint32_t ll[] = {0, 1, 7, 10, 100, 236, 237, 240};
  static const uint32_t cl[] = {0, 1, 32, 100, 200};
  static const uint32_t ol[] = {0, 1, 12, 16, 32, 33};
  for (unsigned a = 0; a < sizeof ll / 4; a++)
    for (unsigned c = 0; c < sizeof cl / 4; c++)
      for (unsigned o = 0; o < sizeof ol / 4; o++) {
        for (int i = 0; i < 32; i++) key[i] = rnd();
        for (uint32_t i = 0; i < ll[a]; i++) label[i] = (char)('a' + rnd() % 26);
        label[ll[a]] = 0;
        for (uint32_t i = 0; i < cl[c]; i++) ctx[i] = rnd();
        for (int i = 0; i < 32; i++) o1[i] = o2[i] = 0x55;
        int r1 = ref_expand(key, label, ctx, cl[c], o1, ol[o]);
        int r2 = (int)kotoba_aiueos_tls13_hkdf_expand_label(key, 32, (const uint8_t *)label, ll[a], ctx, cl[c], o2, ol[o]);
        n++; if ((r1 != 0) != (r2 != 0) || !same(o1, o2)) { bad++; puts_("HKDF-DIFF "); hex(ll[a], 3); hex(cl[c], 3); hex(ol[o], 2); putc_('\n'); }
      }
  /* non-canonical lengths are refused */
  hex((uint64_t)kotoba_aiueos_tls13_hmac(key, 20 | (1ull << 32), data, 8, o2), 1);
  hex((uint64_t)kotoba_aiueos_tls13_hkdf_expand_label(key, 32, (const uint8_t *)"key", 3 | (1ull << 40), 0, 0, o2, 16), 1);
  putc_('\n'); puts_("CASES "); hex(n, 4); puts_("DIFFS "); hex(bad, 4); putc_('\n'); puts_("DONE\n");
}
