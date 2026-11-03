#include <stdint.h>
extern int64_t kotoba_aiueos_tls13_clienthello(const uint8_t *, uint64_t, const uint8_t *, uint64_t, const uint8_t *, uint64_t, uint8_t *, uint64_t);
extern int64_t kotoba_aiueos_tls13_serverhello_parse(const uint8_t *, uint64_t, uint8_t *, uint64_t);
#define TLS_CH_MAX 256
static uint16_t be16(const uint8_t *p) {
  return (uint16_t)(((uint32_t)p[0] << 8) | p[1]);
}

static uint32_t be24(const uint8_t *p) {
  return ((uint32_t)p[0] << 16) | ((uint32_t)p[1] << 8) | p[2];
}

static void put16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v;
}

static void copy_bytes(uint8_t *d, const uint8_t *s, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; i++) d[i] = s[i];
}

static const uint8_t ch_template[157] = {
  0x16,0x03,0x01,0x00,0x98,0x01,0x00,0x00,0x94,0x03,0x03,0xa1,0xe0,0xa1,0xe0,
  0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,
  0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0xa1,0xe0,0x00,0x00,
  0x02,0x13,0x01,0x01,0x00,0x00,0x69,0x00,0x00,0x00,0x11,0x00,0x0f,0x00,0x00,
  0x0c,0x6b,0x6f,0x74,0x6f,0x62,0x61,0x73,0x65,0x2e,0x6e,0x65,0x74,0x00,0x0a,
  0x00,0x04,0x00,0x02,0x00,0x1d,0x00,0x0d,0x00,0x08,0x00,0x06,0x04,0x03,0x08,
  0x04,0x04,0x01,0x00,0x2b,0x00,0x03,0x02,0x03,0x04,0x00,0x10,0x00,0x0b,0x00,
  0x09,0x08,0x68,0x74,0x74,0x70,0x2f,0x31,0x2e,0x31,0x00,0x33,0x00,0x26,0x00,
  0x24,0x00,0x1d,0x00,0x20,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0a,
  0x0b,0x0c,0x0d,0x0e,0x0f,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19,
  0x1a,0x1b,0x1c,0x1d,0x1e,0x1f,0x20};

static int ref_serverhello(const uint8_t *hs, uint32_t n, uint8_t out_pub[32]) {
  uint32_t off, ext_end, sid;
  uint8_t server_pub[32];
  int got_share = 0, got_13 = 0;
  if (n < 40 || hs[0] != 0x02) return 0;
  if (be24(hs + 1) + 4 != n) return 0;
  if (hs[4] != 0x03 || hs[5] != 0x03) return 0;
  sid = hs[38];
  if (sid > 32 || 39 + sid + 3 + 2 > n) return 0;
  off = 39 + sid;
  if (hs[off] != 0x13 || hs[off + 1] != 0x01) return 0; /* AES-128-GCM */
  off += 2;
  if (hs[off] != 0) return 0;
  off++;
  if (off + 2 > n) return 0;
  ext_end = off + 2 + be16(hs + off);
  off += 2;
  if (ext_end != n) return 0;
  while (off + 4 <= ext_end) {
    uint16_t typ = be16(hs + off);
    uint16_t elen = be16(hs + off + 2);
    const uint8_t *ed = hs + off + 4;
    if (off + 4 + elen > ext_end) return 0;
    if (typ == 0x002b && elen >= 2 && ed[elen - 2] == 0x03 && ed[elen - 1] == 0x04)
      got_13 = 1;
    if (typ == 0x0033 && elen >= 36 && be16(ed) == 0x001d && be16(ed + 2) == 32) {
      copy_bytes(server_pub, ed + 4, 32);
      got_share = 1;
    }
    off += 4 + elen;
  }
  if (!got_13 || !got_share) return 0;
  copy_bytes(out_pub, server_pub, 32);
  return 1;
}

static int ref_clienthello(int configured, const uint8_t *configured_host, uint32_t configured_host_len, const uint8_t *configured_random, const uint8_t *client_pub, uint8_t *ch_record, uint32_t *ch_record_len) {
  const uint8_t *host = configured ? configured_host :
    (const uint8_t *)"kotobase.net";
  uint32_t host_len = configured ? configured_host_len :
    12u;
  const uint8_t *tail = ch_template + 73;
  uint32_t tail_len = (uint32_t)sizeof(ch_template) - 73;
  uint32_t total = 61 + host_len + tail_len;
  uint32_t record_payload = total - 5;
  uint32_t handshake_payload = total - 9;
  uint32_t extensions_len = 93 + host_len;
  uint32_t sni_ext_len = 5 + host_len;
  uint32_t sni_list_len = 3 + host_len;
  uint32_t i;
  if (total > TLS_CH_MAX || host_len > 255) return 0;
  copy_bytes(ch_record, ch_template, 61);
  put16(ch_record + 3, (uint16_t)record_payload);
  ch_record[6] = (uint8_t)(handshake_payload >> 16);
  ch_record[7] = (uint8_t)(handshake_payload >> 8);
  ch_record[8] = (uint8_t)handshake_payload;
  if (configured) copy_bytes(ch_record + 11, configured_random, 32);
  put16(ch_record + 50, (uint16_t)extensions_len);
  put16(ch_record + 54, (uint16_t)sni_ext_len);
  put16(ch_record + 56, (uint16_t)sni_list_len);
  put16(ch_record + 59, (uint16_t)host_len);
  copy_bytes(ch_record + 61, host, host_len);
  copy_bytes(ch_record + 61 + host_len, tail, tail_len);
  for (i = 0; i < 32; i++)
    ch_record[113 + host_len + i] = client_pub[i];
  *ch_record_len = total;
  return 1;
}

static void putc_(char c) { __asm__ volatile("outb %0, %1" :: "a"(c), "Nd"((uint16_t)0xe9)); }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void hex(uint64_t v, int n) { for (int i = n - 1; i >= 0; i--) putc_("0123456789abcdef"[(v >> (4 * i)) & 15]); putc_(' '); }
static uint32_t seed = 5;
static uint32_t rnd(void) { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static uint8_t buf[4096], k1[32], k2[32], c1[256], c2[256], host[256], rnd32[32], pub[32];
static unsigned n_cases, n_ok, n_bad;
static uint32_t ext(uint8_t *p, uint16_t typ, const uint8_t *data, uint16_t len) {
  p[0] = typ >> 8; p[1] = typ; p[2] = len >> 8; p[3] = len; for (uint16_t i = 0; i < len; i++) p[4 + i] = data[i]; return 4u + len;
}
static uint32_t make_sh(uint8_t *p, uint32_t sid, int shares, int with13, int order) {
  uint8_t share[36], ver[2] = {3, 4}, junk[7];
  uint32_t o = 0, e;
  p[o++] = 2; o += 3; p[o++] = 3; p[o++] = 3;
  for (int i = 0; i < 32; i++) p[o++] = (uint8_t)rnd();
  p[o++] = (uint8_t)sid; for (uint32_t i = 0; i < sid; i++) p[o++] = (uint8_t)rnd();
  p[o++] = 0x13; p[o++] = 0x01; p[o++] = 0;
  e = o; o += 2;
  for (int k = 0; k < 7; k++) junk[k] = (uint8_t)rnd();
  if (order) o += ext(p + o, 0x0017, junk, 7);
  if (with13 && !order) o += ext(p + o, 0x002b, ver, 2);
  for (int s = 0; s < shares; s++) {
    share[0] = 0; share[1] = 0x1d; share[2] = 0; share[3] = 32;
    for (int k = 4; k < 36; k++) share[k] = (uint8_t)rnd();
    o += ext(p + o, 0x0033, share, 36);
  }
  if (with13 && order) o += ext(p + o, 0x002b, ver, 2);
  p[e] = (uint8_t)((o - e - 2) >> 8); p[e + 1] = (uint8_t)(o - e - 2);
  p[1] = (uint8_t)((o - 4) >> 16); p[2] = (uint8_t)((o - 4) >> 8); p[3] = (uint8_t)(o - 4);
  return o;
}
static void sh_case(uint32_t n, unsigned tag) {
  for (int i = 0; i < 32; i++) k1[i] = k2[i] = 0x77;
  int r1 = ref_serverhello(buf, n, k1);
  int r2 = (int)kotoba_aiueos_tls13_serverhello_parse(buf, n, k2, 32);
  int same = (r1 != 0) == (r2 != 0);
  if (r1) for (int i = 0; i < 32; i++) if (k1[i] != k2[i]) same = 0;
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; puts_("SH-DIFF "); hex(n, 4); hex(tag, 4); hex(r1, 1); hex(r2, 1); putc_('\n'); }
}
static void ch_case(int configured, uint32_t hl) {
  uint32_t l1 = 0;
  for (int i = 0; i < 256; i++) c1[i] = c2[i] = 0x5a;
  int r1 = ref_clienthello(configured, host, hl, rnd32, pub, c1, &l1);
  int64_t r2 = kotoba_aiueos_tls13_clienthello(configured ? host : (const uint8_t *)"kotobase.net", configured ? hl : 12,
                                               rnd32, configured ? 32 : 0, pub, 32, c2, 256);
  int same = r1 ? (r2 == (int64_t)l1) : (r2 == 0);
  for (int i = 0; i < 256; i++) if (c1[i] != c2[i] && r1) same = 0;
  n_cases++; if (r1) n_ok++;
  if (!same) { n_bad++; puts_("CH-DIFF "); hex(configured, 1); hex(hl, 3); hex(r1, 1); hex((uint64_t)r2, 4); putc_('\n'); }
}
void test_main(void) {
  puts_("HELLODIFF\n");
  for (uint32_t sid = 0; sid <= 33; sid += 1)
    for (int shares = 0; shares <= 2; shares++)
      for (int with13 = 0; with13 <= 1; with13++)
        for (int order = 0; order <= 1; order++) {
          uint32_t n = make_sh(buf, sid, shares, with13, order);
          sh_case(n, sid * 100 + shares * 10 + with13 * 2 + order);
          sh_case(n - 1, 1); sh_case(n + 1, 2);
        }
  for (unsigned k = 0; k < 6000; k++) {
    uint32_t n = make_sh(buf, rnd() % 33, 1 + rnd() % 2, 1, rnd() & 1);
    unsigned flips = 1 + rnd() % 2;
    for (unsigned f = 0; f < flips; f++) buf[rnd() % n] = (uint8_t)rnd();
    sh_case((rnd() % 10 == 0) ? rnd() % (n + 4) : n, k);
  }
  for (int i = 0; i < 32; i++) { rnd32[i] = (uint8_t)rnd(); pub[i] = (uint8_t)rnd(); }
  for (uint32_t hl = 0; hl <= 255; hl++) {
    for (uint32_t i = 0; i < hl; i++) host[i] = (uint8_t)('a' + rnd() % 26);
    ch_case(1, hl);
  }
  ch_case(0, 0);
  puts_("CASES "); hex(n_cases, 5); puts_("ACCEPTED "); hex(n_ok, 5); puts_("DIFFS "); hex(n_bad, 5); putc_('\n'); puts_("DONE\n");
}
