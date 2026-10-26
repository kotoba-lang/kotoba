#include "tls13.h"
#include "tls_aes_gcm.h"

extern uint64_t kotoba_aiueos_sha256(const uint8_t *, uint64_t, uint8_t[32],
                                     uint8_t *, uint64_t);
extern uint64_t kotoba_aiueos_x25519(const uint8_t *, const uint8_t *,
                                     uint8_t *, uint8_t *);
extern uint64_t kotoba_aiueos_ecdsa_p256_sha256_verify(
    const uint8_t *, const uint8_t *, const uint8_t *, uint8_t *, uint64_t);
/* The TLS 1.3 AEAD and record layer (ADR-0132, ADR-0133). Both return a
   REASON CODE and ZERO IS SUCCESS -- the opposite of the C in this file, so
   every call site has to be written rather than transcribed. */
extern uint64_t kotoba_aiueos_aes128_gcm(uint8_t *, uint64_t, uint8_t *,
                                         uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_tls13_record(uint8_t *, uint64_t, uint8_t *,
                                           uint64_t, uint64_t);

#define TLS_TR_MAX 12288
#define TLS_RX_MAX 12288
#define TLS_APP_MAX 4096
#define TLS_HS_MAX 12288
/* Where the big buffers live: the kernel's `.high_bss` window; on the host
   probe (a Mach-O or ELF userland with no such section) plain statics. */
#ifdef AIUEOS_TLS13_HOST_PROBE
#define TLS_SCRATCH
#else
#define TLS_SCRATCH __attribute__((section(".high_bss"), aligned(64)))
#endif
#define TLS_HOST_MAX 63
#define TLS_HTTP_MAX 1024
#define TLS_CH_MAX 256

#ifdef AIUEOS_TLS13_HOST_PROBE
#define AIUEOS_TLS_HIGH_BSS
#else
#define AIUEOS_TLS_HIGH_BSS __attribute__((section(".high_bss")))
#endif

/* `.high_bss` (4..6 MiB), not `.bss`: the 2026-10-26 merge of main into the
   scorecard branch pushed `aiueos_low_end` to 0x1f5000, one page past
   linker.ld's 0x1f4000 assert. These three are CPU-only scratch reached from
   the selftests and the handshake, both after `main.c` zeroes the section. */
static uint8_t TLS_SCRATCH sha_ws[512];
static uint8_t TLS_SCRATCH x_ws[646];
static uint8_t TLS_SCRATCH ecdsa_ws[2048];
static uint8_t leaf_pub[64];
static int have_leaf_pub;
static int certverify_ok;
static int certverify_parsed;
static uint16_t certverify_scheme;
static uint8_t cv_rs[64];
static uint8_t cv_digest[32];
/* The four record/transcript buffers live in `.high_bss` (4..6 MiB), not
   `.bss`, since ADR-0221: the Kotoba objects grew the low 2 MiB past
   `aiueos_low_end`, and 61 KiB of TLS scratch was the cheapest thing to move.
   `main.c` zeroes the section at entry, so they start zero as they did. */
static uint8_t TLS_SCRATCH hmac_block[64 + TLS_TR_MAX];

static uint8_t TLS_SCRATCH transcript[TLS_TR_MAX];
static uint32_t transcript_len;
static uint8_t TLS_SCRATCH rx[TLS_RX_MAX];
static uint32_t rx_len;
static uint8_t TLS_SCRATCH hs_partial[TLS_HS_MAX];
static uint32_t hs_partial_len;
/* Application plaintext and the record decrypt staging are needed only after
   owned paging is live.  Keep them in the writable/NX 4..6 MiB kernel window
   so persistent worker telemetry does not consume the bounded low W^X
   aperture shared with admitted user text. */
static uint8_t app_buf[TLS_APP_MAX]
  AIUEOS_TLS_HIGH_BSS;
static uint32_t app_len;

static uint8_t client_scalar[32];
static uint8_t client_pub[32];
static uint8_t ch_record[TLS_CH_MAX];
static uint32_t ch_record_len;

/* A profile is mechanism, not server admission: callers choose the exact SNI,
   HTTP request, ClientHello random and X25519 scalar before reset/handshake.
   Keeping bounded copies here lets the physical RTL8125 profile use the same
   record engine without retaining pointers to transient boot memory. The
   default below preserves the original kotobase smoke byte-for-byte. */
static uint8_t configured_host[TLS_HOST_MAX] AIUEOS_TLS_HIGH_BSS;
static uint32_t configured_host_len;
static uint8_t configured_http[TLS_HTTP_MAX] AIUEOS_TLS_HIGH_BSS;
static uint32_t configured_http_len;
static uint8_t configured_random[32];
static uint8_t configured_scalar[32];
static int configured;

static uint8_t c_hs_key[16], c_hs_iv[12], s_hs_key[16], s_hs_iv[12];
static uint8_t c_ap_key[16], c_ap_iv[12], s_ap_key[16], s_ap_iv[12];
static uint8_t handshake_secret[32];
static uint8_t c_hs_secret[32], s_hs_secret[32];
static uint64_t s_hs_seq, c_hs_seq, s_ap_seq, c_ap_seq;

static int saw_record;
static uint8_t first_record_type;
static int have_sh;
static int have_hs_keys;
static int have_server_finished;
static int handshake_ready;
static int failed;
static uint8_t last_record_type;
static uint8_t last_inner_type;

static const uint8_t x25519_base[32] = {9};
/* Smoke-only ephemeral. Not the RFC 7748 test scalar. Clamped by the object. */
static const uint8_t smoke_scalar[32] = {
  0x5a,0x1e,0x05,0x13,0xc1,0x0d,0x15,0x07,0xa1,0xe0,0x53,0x00,0x6b,0x6f,0x74,0x6f,
  0x62,0x61,0x73,0x65,0x2e,0x6e,0x65,0x74,0x13,0x01,0x03,0x04,0x00,0x1d,0x00,0x20};

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

static const uint8_t default_http_get[] =
  "GET /ipfs/bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku HTTP/1.1\r\n"
  "Host: kotobase.net\r\n"
  "User-Agent: aiueos-p2\r\n"
  "Accept: */*\r\n"
  "Connection: close\r\n"
  "\r\n";

static const char default_host[] = "kotobase.net";

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
static void zero_bytes(uint8_t *d, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; i++) d[i] = 0;
}

static int hostname_ok(const char *host, uint32_t *length) {
  uint32_t n = 0;
  uint32_t label_len = 0;
  int label_has_byte = 0;
  int last_hyphen = 0;
  if (!host || !length) return 0;
  while (host[n]) {
    uint8_t c = (uint8_t)host[n];
    if (n >= TLS_HOST_MAX) return 0;
    if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
      label_has_byte = 1;
      label_len++;
      last_hyphen = 0;
    } else if (c == '-') {
      if (!label_has_byte) return 0;
      label_len++;
      last_hyphen = 1;
    } else if (c == '.') {
      if (!label_has_byte || last_hyphen || label_len > 63) return 0;
      label_has_byte = 0;
      label_len = 0;
      last_hyphen = 0;
    } else {
      return 0;
    }
    n++;
  }
  if (!n || !label_has_byte || last_hyphen || label_len > 63) return 0;
  *length = n;
  return 1;
}

int aiueos_tls13_configure(const char *host,
                           const uint8_t *request, uint32_t request_len,
                           const uint8_t client_random[32],
                           const uint8_t ephemeral_scalar[32]) {
  uint32_t host_len = 0, i;
  uint8_t random_or = 0, scalar_or = 0;
  if (!hostname_ok(host, &host_len) || !request || !request_len ||
      request_len > TLS_HTTP_MAX || !client_random || !ephemeral_scalar)
    return 0;
  for (i = 0; i < 32; i++) {
    random_or |= client_random[i];
    scalar_or |= ephemeral_scalar[i];
  }
  if (!random_or || !scalar_or) return 0;
  copy_bytes(configured_host, (const uint8_t *)host, host_len);
  configured_host_len = host_len;
  copy_bytes(configured_http, request, request_len);
  configured_http_len = request_len;
  copy_bytes(configured_random, client_random, 32);
  copy_bytes(configured_scalar, ephemeral_scalar, 32);
  configured = 1;
  return 1;
}

static int clienthello_build(void) {
  const uint8_t *host = configured ? configured_host :
    (const uint8_t *)default_host;
  uint32_t host_len = configured ? configured_host_len :
    (uint32_t)(sizeof(default_host) - 1);
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
  ch_record_len = total;
  return 1;
}

static int sha256(const uint8_t *in, uint32_t n, uint8_t out[32]) {
  static const uint8_t empty[1] = {0};
  const uint8_t *p = (n == 0) ? empty : in;
  return (int)kotoba_aiueos_sha256(p, n, out, sha_ws, sizeof(sha_ws));
}

static int hmac_sha256(const uint8_t *key, uint32_t key_len,
                       const uint8_t *data, uint32_t data_len, uint8_t out[32]) {
  uint8_t ipad[64], opad[64], inner[32];
  uint32_t i;
  uint8_t kh[32];
  const uint8_t *k = key;
  uint32_t klen = key_len;
  if (64 + data_len > 12288) return 0;
  if (klen > 64) {
    if (!sha256(key, klen, kh)) return 0;
    k = kh;
    klen = 32;
  }
  for (i = 0; i < 64; i++) {
    uint8_t b = (i < klen) ? k[i] : 0;
    ipad[i] = (uint8_t)(b ^ 0x36);
    opad[i] = (uint8_t)(b ^ 0x5c);
  }
  copy_bytes(hmac_block, ipad, 64);
  copy_bytes(hmac_block + 64, data, data_len);
  if (!sha256(hmac_block, 64 + data_len, inner)) return 0;
  copy_bytes(hmac_block, opad, 64);
  copy_bytes(hmac_block + 64, inner, 32);
  return sha256(hmac_block, 96, out);
}

static int hkdf_extract(const uint8_t *salt, uint32_t salt_len,
                        const uint8_t *ikm, uint32_t ikm_len, uint8_t out[32]) {
  static const uint8_t zeros[32] = {0};
  if (!salt || salt_len == 0) {
    salt = zeros;
    salt_len = 32;
  }
  return hmac_sha256(salt, salt_len, ikm, ikm_len, out);
}

static int hkdf_expand_label(const uint8_t *secret, const char *label,
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
  if (!hmac_sha256(secret, 32, info, infolen + 1, full)) return 0;
  copy_bytes(out, full, out_len);
  return 1;
}

static int derive_secret(const uint8_t *secret, const char *label,
                         const uint8_t *msgs, uint32_t msgs_len, uint8_t out[32]) {
  uint8_t th[32];
  if (!sha256(msgs, msgs_len, th)) return 0;
  return hkdf_expand_label(secret, label, th, 32, out, 32);
}

static int transcript_add(const uint8_t *p, uint32_t n) {
  if (transcript_len + n > TLS_TR_MAX) return 0;
  copy_bytes(transcript + transcript_len, p, n);
  transcript_len += n;
  return 1;
}

/* The record layer is `os/aiueos/kotoba/tls13-record.kotoba`, compiled to
   `kotoba_aiueos_tls13_record` (ADR-0133).  What was here -- `make_nonce`,
   `protect` and `unprotect`, 52 lines -- is gone, and it was not plumbing:
   the 5-byte header is the AAD, so a length taken from the wrong place is a
   forgery the AEAD accepts; the sequence number is XORed into the nonce, so a
   reused sequence is a reused keystream; the inner content type is the last
   non-zero plaintext byte, so a padding strip that stops one byte early hands
   the caller the wrong record type.

   THE OBJECT RETURNS A REASON CODE AND ZERO IS SUCCESS.  These two wrappers
   keep the 1-is-success shape their callers were written against, and the
   inversion happens on the `return` lines below and nowhere else.

   THE RECORD IS TRANSFORMED IN PLACE.  SEAL wants the plaintext already at
   `out + 5`; OPEN decrypts `rec` where it lies.  That is exact rather than a
   shortcut -- CTR is an XOR -- and it is why `decrypt_plain`, 12 KiB of
   `.high_bss`, and `protect`'s 2 KiB `inner` stack buffer are both gone. */
static uint8_t record_ctx[1280];

static void record_ctx_open(const uint8_t key[16], const uint8_t iv[12],
                            uint64_t seq) {
  uint32_t i;
  for (i = 0; i < sizeof(record_ctx); i++) record_ctx[i] = 0;
  copy_bytes(record_ctx, key, 16);
  copy_bytes(record_ctx + 16, iv, 12);
  for (i = 0; i < 8; i++)
    record_ctx[48 + i] = (uint8_t)(seq >> (56 - 8 * i));
}

static int protect(const uint8_t key[16], const uint8_t iv[12], uint64_t seq,
                   uint8_t inner_type, const uint8_t *pt, uint32_t pt_len,
                   uint8_t *out, uint32_t *out_len) {
  if (pt_len > 12287) return 0;
  record_ctx_open(key, iv, seq);
  record_ctx[56] = inner_type;
  record_ctx[58] = (uint8_t)(pt_len >> 8);
  record_ctx[59] = (uint8_t)(pt_len & 0xff);
  copy_bytes(out + 5, pt, pt_len);
  if (kotoba_aiueos_tls13_record(record_ctx, sizeof(record_ctx), out,
                                 (uint64_t)pt_len + 22u, 1) != 0)
    return 0;
  *out_len = (uint32_t)record_ctx[60] * 256u + record_ctx[61];
  return 1;
}

/* `rec` is written, not read: OPEN decrypts in place.  The caller owns a
   mutable receive buffer (`rx`), which is where records arrive anyway. */
static int unprotect(const uint8_t key[16], const uint8_t iv[12], uint64_t seq,
                     uint8_t *rec, uint32_t rec_len,
                     uint8_t *pt, uint32_t *pt_len, uint8_t *inner_type) {
  if (rec_len < 22 || rec_len > 12310) return 0;
  record_ctx_open(key, iv, seq);
  if (kotoba_aiueos_tls13_record(record_ctx, sizeof(record_ctx), rec,
                                 (uint64_t)rec_len, 0) != 0)
    return 0;
  *inner_type = record_ctx[56];
  *pt_len = (uint32_t)record_ctx[58] * 256u + record_ctx[59];
  copy_bytes(pt, rec + 5, *pt_len);
  return 1;
}

static int derive_hs_keys(const uint8_t *server_pub) {
  uint8_t shared[32], early[32], derived[32], empty_ikm[32];
  uint8_t c_hs[32], s_hs[32];
  zero_bytes(empty_ikm, 32);
  if (!kotoba_aiueos_x25519(client_scalar, server_pub, shared, x_ws)) return 0;
  if (!hkdf_extract(0, 0, empty_ikm, 32, early)) return 0;
  if (!derive_secret(early, "derived", 0, 0, derived)) return 0;
  if (!hkdf_extract(derived, 32, shared, 32, handshake_secret)) return 0;
  if (!derive_secret(handshake_secret, "c hs traffic", transcript, transcript_len, c_hs))
    return 0;
  if (!derive_secret(handshake_secret, "s hs traffic", transcript, transcript_len, s_hs))
    return 0;
  if (!hkdf_expand_label(c_hs, "key", 0, 0, c_hs_key, 16)) return 0;
  if (!hkdf_expand_label(c_hs, "iv", 0, 0, c_hs_iv, 12)) return 0;
  if (!hkdf_expand_label(s_hs, "key", 0, 0, s_hs_key, 16)) return 0;
  if (!hkdf_expand_label(s_hs, "iv", 0, 0, s_hs_iv, 12)) return 0;
  copy_bytes(c_hs_secret, c_hs, 32);
  copy_bytes(s_hs_secret, s_hs, 32);
  have_hs_keys = 1;
  s_hs_seq = 0;
  c_hs_seq = 0;
  return 1;
}

static int derive_ap_keys(void) {
  uint8_t derived[32], master[32], zeros[32], c_ap[32], s_ap[32];
  zero_bytes(zeros, 32);
  if (!derive_secret(handshake_secret, "derived", 0, 0, derived)) return 0;
  if (!hkdf_extract(derived, 32, zeros, 32, master)) return 0;
  if (!derive_secret(master, "c ap traffic", transcript, transcript_len, c_ap))
    return 0;
  if (!derive_secret(master, "s ap traffic", transcript, transcript_len, s_ap))
    return 0;
  if (!hkdf_expand_label(c_ap, "key", 0, 0, c_ap_key, 16)) return 0;
  if (!hkdf_expand_label(c_ap, "iv", 0, 0, c_ap_iv, 12)) return 0;
  if (!hkdf_expand_label(s_ap, "key", 0, 0, s_ap_key, 16)) return 0;
  if (!hkdf_expand_label(s_ap, "iv", 0, 0, s_ap_iv, 12)) return 0;
  s_ap_seq = 0;
  c_ap_seq = 0;
  return 1;
}

static int parse_serverhello(const uint8_t *hs, uint32_t n) {
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
  if (!transcript_add(hs, n)) return 0;
  have_sh = 1;
  return derive_hs_keys(server_pub);
}

static int finish_check(const uint8_t *verify, uint32_t n) {
  uint8_t finished_key[32], th[32], expect[32];
  uint32_t i, diff = 0;
  if (n != 32) return 0;
  if (!hkdf_expand_label(s_hs_secret, "finished", 0, 0, finished_key, 32)) return 0;
  if (!sha256(transcript, transcript_len, th)) return 0;
  if (!hmac_sha256(finished_key, 32, th, 32, expect)) return 0;
  for (i = 0; i < 32; i++) diff |= (uint32_t)(verify[i] ^ expect[i]);
  if (diff) return 0;
  have_server_finished = 1;
  return 1;
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

static int parse_certificate(const uint8_t *hs, uint32_t n) {
  if (n < 8 || hs[0] != 0x0b) return 0;
  if (be24(hs + 1) + 4 != n) return 0;
  if (!find_p256_point(hs, n, leaf_pub)) return 0;
  have_leaf_pub = 1;
  return 1;
}

static int verify_certificate_verify(const uint8_t *hs, uint32_t n) {
  uint32_t mlen, siglen, i;
  uint8_t th[32], digest[32], rs[64], content[130];
  static const uint8_t ctx[33] = {
    'T','L','S',' ','1','.','3',',',' ','s','e','r','v','e','r',' ',
    'C','e','r','t','i','f','i','c','a','t','e','V','e','r','i','f','y'};
  if (!have_leaf_pub) return 0;
  if (n < 8 || hs[0] != 0x0f) return 0;
  mlen = be24(hs + 1);
  if (mlen + 4 != n) return 0;
  certverify_scheme = be16(hs + 4);
  if (certverify_scheme != 0x0403) return 0; /* ecdsa_secp256r1_sha256 */
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
  certverify_parsed = 1;
  return 1;
}

int aiueos_tls13_run_certverify(void) {
  /* TCP ACK of the server flight happens first. Kotoba ECDSA is seconds of
     TCG; doing it inside feed delayed the ACK until the peer had moved on,
     so HTTP GET never got a body (app=0 after get=1). */
  if (!certverify_parsed || !have_leaf_pub) return 0;
  if (!kotoba_aiueos_ecdsa_p256_sha256_verify(cv_rs, cv_digest, leaf_pub,
                                              ecdsa_ws, 2048))
    return 0;
  certverify_ok = 1;
  return 1;
}

static int consume_hs_messages(const uint8_t *p, uint32_t n) {
  if (hs_partial_len + n > TLS_HS_MAX) return 0;
  copy_bytes(hs_partial + hs_partial_len, p, n);
  hs_partial_len += n;
  while (hs_partial_len >= 4) {
    uint32_t mlen = be24(hs_partial + 1);
    uint32_t total = 4 + mlen;
    uint8_t typ = hs_partial[0];
    if (total > TLS_HS_MAX) return 0;
    if (hs_partial_len < total) return 1;
    if (typ == 0x14) {
      if (!certverify_parsed) return 0;
      if (!finish_check(hs_partial + 4, mlen)) return 0;
      if (!transcript_add(hs_partial, total)) return 0;
      if (!derive_ap_keys()) return 0;
      handshake_ready = 1;
    } else if (typ == 0x0b) {
      if (!parse_certificate(hs_partial, total)) return 0;
      if (!transcript_add(hs_partial, total)) return 0;
    } else if (typ == 0x0f) {
      /* Hash transcript BEFORE adding CertificateVerify (RFC 8446 4.4.3). */
      if (!verify_certificate_verify(hs_partial, total)) return 0;
      if (!transcript_add(hs_partial, total)) return 0;
    } else if (!have_server_finished) {
      /* EE / others before Finished. Do not hash NST after Finished. */
      if (!transcript_add(hs_partial, total)) return 0;
    }
    if (hs_partial_len > total)
      copy_bytes(hs_partial, hs_partial + total, hs_partial_len - total);
    hs_partial_len -= total;
  }
  return 1;
}

static uint32_t nst_count;

static uint8_t last_alert_level;
static uint8_t last_alert_desc;

static int process_record(uint8_t *rec, uint32_t rec_len) {
  uint8_t typ = rec[0];
  last_record_type = typ;
  if (!saw_record) {
    saw_record = 1;
    first_record_type = typ;
  }
  if (typ == 0x14) return 1; /* CCS */
  if (typ == 0x15) {
    if (rec_len >= 7) {
      last_alert_level = rec[5];
      last_alert_desc = rec[6];
    }
    failed = 1;
    return 0;
  }
  if (typ == 0x16) {
    uint32_t hlen = (uint32_t)be16(rec + 3);
    if (handshake_ready) return 1;
    if (!have_sh) return parse_serverhello(rec + 5, hlen);
    return consume_hs_messages(rec + 5, hlen);
  }
  if (typ == 0x17) {
    uint8_t inner;
    uint32_t plen = 0;
    static uint8_t TLS_SCRATCH plain[TLS_HS_MAX];
    if (!have_hs_keys) return 0;
    if (!handshake_ready) {
      if (!unprotect(s_hs_key, s_hs_iv, s_hs_seq, rec, rec_len, plain, &plen, &inner))
        return 0;
      s_hs_seq++;
      last_inner_type = inner;
      if (inner == 0x15) {
        if (plen >= 2) {
          last_alert_level = plain[0];
          last_alert_desc = plain[1];
        }
        failed = 1;
        return 0;
      }
      if (inner != 0x16) return 0;
      return consume_hs_messages(plain, plen);
    }
    if (!unprotect(s_ap_key, s_ap_iv, s_ap_seq, rec, rec_len, plain, &plen, &inner))
      return 0;
    s_ap_seq++;
    last_inner_type = inner;
    if (inner == 0x15) {
      if (plen >= 2) {
        last_alert_level = plain[0];
        last_alert_desc = plain[1];
      }
      /* close_notify (warning/0): prior application data stays valid. */
      if (plen >= 2 && plain[0] == 1 && plain[1] == 0) return 1;
      failed = 1;
      return 0;
    }
    if (inner != 0x17) {
      nst_count++;
      return 1; /* NST and other post-handshake */
    }
    if (app_len + plen > TLS_APP_MAX) return 0;
    copy_bytes(app_buf + app_len, plain, plen);
    app_len += plen;
    return 1;
  }
  return 1;
}

void aiueos_tls13_reset(void) {
  transcript_len = 0;
  rx_len = 0;
  hs_partial_len = 0;
  app_len = 0;
  saw_record = 0;
  first_record_type = 0;
  have_sh = 0;
  have_hs_keys = 0;
  have_server_finished = 0;
  handshake_ready = 0;
  failed = 0;
  last_record_type = 0;
  last_inner_type = 0;
  last_alert_level = 0;
  last_alert_desc = 0;
  nst_count = 0;
  ch_record_len = 0;
  have_leaf_pub = 0;
  certverify_ok = 0;
  certverify_parsed = 0;
  certverify_scheme = 0;
  s_hs_seq = c_hs_seq = s_ap_seq = c_ap_seq = 0;
}

int aiueos_tls13_clienthello(uint8_t *out, uint32_t *len) {
  copy_bytes(client_scalar, configured ? configured_scalar : smoke_scalar, 32);
  if (!kotoba_aiueos_x25519(client_scalar, x25519_base, client_pub, x_ws)) return 0;
  if (!clienthello_build()) return 0;
  if (!transcript_add(ch_record + 5, ch_record_len - 5)) return 0;
  copy_bytes(out, ch_record, ch_record_len);
  *len = ch_record_len;
  return 1;
}

int aiueos_tls13_feed(const uint8_t *data, uint32_t len) {
  if (failed) return 0;
  if (rx_len + len > TLS_RX_MAX) return 0;
  copy_bytes(rx + rx_len, data, len);
  rx_len += len;
  while (rx_len >= 5) {
    uint32_t rec_len = 5u + (uint32_t)be16(rx + 3);
    if (rec_len < 5 || rec_len > TLS_RX_MAX) {
      failed = 1;
      return 0;
    }
    if (rx_len < rec_len) return 1;
    if (!process_record(rx, rec_len)) {
      failed = 1;
      return 0;
    }
    if (rx_len > rec_len) copy_bytes(rx, rx + rec_len, rx_len - rec_len);
    rx_len -= rec_len;
  }
  return 1;
}

int aiueos_tls13_saw_record(void) { return saw_record; }
uint8_t aiueos_tls13_first_record_type(void) { return first_record_type; }
int aiueos_tls13_handshake_ready(void) { return handshake_ready && !failed; }

int aiueos_tls13_take_finished(uint8_t *out, uint32_t *len) {
  uint8_t finished_key[32], th[32], verify[32], fin[36];
  uint32_t rec_len = 0;
  if (!handshake_ready || !certverify_ok) return 0;
  if (!hkdf_expand_label(c_hs_secret, "finished", 0, 0, finished_key, 32)) return 0;
  if (!sha256(transcript, transcript_len, th)) return 0;
  if (!hmac_sha256(finished_key, 32, th, 32, verify)) return 0;
  fin[0] = 0x14;
  fin[1] = 0;
  fin[2] = 0;
  fin[3] = 32;
  copy_bytes(fin + 4, verify, 32);
  /* Empty legacy_session_id in ClientHello: RFC 8446 D.4 forbids a CCS. */
  if (!protect(c_hs_key, c_hs_iv, c_hs_seq, 0x16, fin, 36, out, &rec_len)) return 0;
  c_hs_seq++;
  *len = rec_len;
  return 1;
}

int aiueos_tls13_take_http(uint8_t *out, uint32_t *len) {
  const uint8_t *request = configured ? configured_http : default_http_get;
  uint32_t rec_len = 0;
  uint32_t request_len = configured ? configured_http_len :
    (uint32_t)(sizeof(default_http_get) - 1);
  if (!handshake_ready) return 0;
  if (!protect(c_ap_key, c_ap_iv, c_ap_seq, 0x17,
               request, request_len, out, &rec_len))
    return 0;
  c_ap_seq++;
  *len = rec_len;
  app_len = 0;
  return 1;
}

uint32_t aiueos_tls13_app_len(void) { return app_len; }
const uint8_t *aiueos_tls13_app(void) { return app_buf; }
int aiueos_tls13_aes_selftest(void) { return aiueos_aes128_gcm_selftest(); }
uint8_t aiueos_tls13_last_record_type(void) { return last_record_type; }
uint8_t aiueos_tls13_last_inner_type(void) { return last_inner_type; }
int aiueos_tls13_failed(void) { return failed; }
uint32_t aiueos_tls13_nst_count(void) { return nst_count; }
uint8_t aiueos_tls13_alert_level(void) { return last_alert_level; }
uint8_t aiueos_tls13_alert_desc(void) { return last_alert_desc; }

uint32_t aiueos_tls13_stage(void) {
  return (saw_record ? 1u : 0u)
       | (have_sh ? 2u : 0u)
       | (have_hs_keys ? 4u : 0u)
       | (have_server_finished ? 8u : 0u)
       | (handshake_ready ? 16u : 0u)
       | (failed ? 32u : 0u)
       | ((uint32_t)first_record_type << 8);
}
uint32_t aiueos_tls13_rx_buffered(void) { return rx_len; }

int aiueos_tls13_certverify_ok(void) { return certverify_ok && !failed; }
uint16_t aiueos_tls13_certverify_scheme(void) { return certverify_scheme; }

int aiueos_tls13_ecdsa_selftest(void) {
  /* RFC 6979 A.2.5 SHA-256 "sample". s+1 must refuse. */
  static const uint8_t sig[64] = {
    0xef,0xd4,0x8b,0x2a,0xac,0xb6,0xa8,0xfd,0x11,0x40,0xdd,0x9c,0xd4,0x5e,0x81,0xd6,
    0x9d,0x2c,0x87,0x7b,0x56,0xaa,0xf9,0x91,0xc3,0x4d,0x0e,0xa8,0x4e,0xaf,0x37,0x16,
    0xf7,0xcb,0x1c,0x94,0x2d,0x65,0x7c,0x41,0xd4,0x36,0xc7,0xa1,0xb6,0xe2,0x9f,0x65,
    0xf3,0xe9,0x00,0xdb,0xb9,0xaf,0xf4,0x06,0x4d,0xc4,0xab,0x2f,0x84,0x3a,0xcd,0xa8};
  static const uint8_t digest[32] = {
    0xaf,0x2b,0xdb,0xe1,0xaa,0x9b,0x6e,0xc1,0xe2,0xad,0xe1,0xd6,0x94,0xf4,0x1f,0xc7,
    0x1a,0x83,0x1d,0x02,0x68,0xe9,0x89,0x15,0x62,0x11,0x3d,0x8a,0x62,0xad,0xd1,0xbf};
  static const uint8_t pub[64] = {
    0x60,0xfe,0xd4,0xba,0x25,0x5a,0x9d,0x31,0xc9,0x61,0xeb,0x74,0xc6,0x35,0x6d,0x68,
    0xc0,0x49,0xb8,0x92,0x3b,0x61,0xfa,0x6c,0xe6,0x69,0x62,0x2e,0x60,0xf2,0x9f,0xb6,
    0x79,0x03,0xfe,0x10,0x08,0xb8,0xbc,0x99,0xa4,0x1a,0xe9,0xe9,0x56,0x28,0xbc,0x64,
    0xf2,0xf1,0xb2,0x0c,0x2d,0x7e,0x9f,0x51,0x77,0xa3,0xc2,0x94,0xd4,0x46,0x22,0x99};
  uint8_t bad[64];
  uint32_t i;
  static uint8_t ws[2048] AIUEOS_TLS_HIGH_BSS;
  if (!kotoba_aiueos_ecdsa_p256_sha256_verify(sig, digest, pub, ws, 2048)) return 0;
  copy_bytes(bad, sig, 64);
  bad[63] = (uint8_t)(bad[63] + 1);
  if (kotoba_aiueos_ecdsa_p256_sha256_verify(bad, digest, pub, ws, 2048)) return 0;
  for (i = 0; i < 2048; i++) ws[i] = 0;
  return 1;
}

int aiueos_tls13_hmac_selftest(void) {
  /* RFC 4231 test case 1. Proves Kotoba SHA-256 HMAC before any handshake. */
  static const uint8_t empty_digest[32] = {
    0xe3,0xb0,0xc4,0x42,0x98,0xfc,0x1c,0x14,0x9a,0xfb,0xf4,0xc8,0x99,0x6f,0xb9,0x24,
    0x27,0xae,0x41,0xe4,0x64,0x9b,0x93,0x4c,0xa4,0x95,0x99,0x1b,0x78,0x52,0xb8,0x55};
  static const uint8_t key[20] = {
    0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,
    0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b};
  static const uint8_t data[8] = {'H','i',' ','T','h','e','r','e'};
  static const uint8_t expect[32] = {
    0xb0,0x34,0x4c,0x61,0xd8,0xdb,0x38,0x53,0x5c,0xa8,0xaf,0xce,0xaf,0x0b,0xf1,0x2b,
    0x88,0x1d,0xc2,0x00,0xc9,0x83,0x3d,0xa7,0x26,0xe9,0x37,0x6c,0x2e,0x32,0xcf,0xf7};
  static const uint8_t ikm[22] = {
    0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,
    0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b,0x0b};
  static const uint8_t salt[13] = {
    0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0a,0x0b,0x0c};
  static const uint8_t prk[32] = {
    0x07,0x77,0x09,0x36,0x2c,0x2e,0x32,0xdf,0x0d,0xdc,0x3f,0x0d,0xc4,0x7b,0xba,0x63,
    0x90,0xb6,0xc7,0x3b,0xb5,0x0f,0x9c,0x31,0x22,0xec,0x84,0x4a,0xd7,0xc2,0xb3,0xe5};
  uint8_t out[32];
  uint32_t i, diff = 0;
  if (!sha256(0, 0, out)) return 0;
  for (i = 0; i < 32; i++) diff |= (uint32_t)(out[i] ^ empty_digest[i]);
  if (diff) return 0;
  if (!hmac_sha256(key, 20, data, 8, out)) return 0;
  for (i = 0; i < 32; i++) diff |= (uint32_t)(out[i] ^ expect[i]);
  if (diff) return 0;
  if (!hkdf_extract(salt, 13, ikm, 22, out)) return 0;
  diff = 0;
  for (i = 0; i < 32; i++) diff |= (uint32_t)(out[i] ^ prk[i]);
  return diff == 0;
}

/* The record layer, executed on the machine that will run it, against a whole
   encrypted record printed in RFC 8448 section 3 beside the traffic keys that
   produced it.  The kernel had a boot self-test for the AEAD, the key schedule
   and the signature and none for the framing around them -- which is the part
   ADR-0133 argues is where a record layer gets exploited.

   The sequence number is 0 here and 1 in the alert that follows it in the RFC;
   this vector is the application_data record, so the nonce XOR is exercised by
   the contract rather than by this test, which exists to prove the OBJECT runs
   and agrees with a published record, not to re-run its 17 vectors. */
int aiueos_tls13_record_selftest(void) {
  static const uint8_t key[16] = {
    0x17,0x42,0x2d,0xda,0x59,0x6e,0xd5,0xd9,0xac,0xd8,0x90,0xe3,0xc6,0x3f,0x50,0x51};
  static const uint8_t iv[12] = {
    0x5b,0x78,0x92,0x3d,0xee,0x08,0x57,0x90,0x33,0xe5,0x23,0xd9};
  static const uint8_t expect[72] = {
    0x17,0x03,0x03,0x00,0x43,0xa2,0x3f,0x70,0x54,0xb6,0x2c,0x94,0xd0,0xaf,0xfa,0xfe,
    0x82,0x28,0xba,0x55,0xcb,0xef,0xac,0xea,0x42,0xf9,0x14,0xaa,0x66,0xbc,0xab,0x3f,
    0x2b,0x98,0x19,0xa8,0xa5,0xb4,0x6b,0x39,0x5b,0xd5,0x4a,0x9a,0x20,0x44,0x1e,0x2b,
    0x62,0x97,0x4e,0x1f,0x5a,0x62,0x92,0xa2,0x97,0x70,0x14,0xbd,0x1e,0x3d,0xea,0xe6,
    0x3a,0xee,0xbb,0x21,0x69,0x49,0x15,0xe4};
  static uint8_t record[128];
  static uint8_t payload[64];
  static uint8_t plain[64];
  uint32_t i, diff = 0, len = 0, plen = 0;
  uint8_t inner = 0;
  for (i = 0; i < 50; i++) payload[i] = (uint8_t)i;
  for (i = 0; i < sizeof(record); i++) record[i] = 0;
  if (!protect(key, iv, 0, 0x17, payload, 50, record, &len)) return 0;
  if (len != 72) return 0;
  for (i = 0; i < 72; i++) diff |= (uint32_t)(record[i] ^ expect[i]);
  if (diff) return 0;
  if (!unprotect(key, iv, 0, record, 72, plain, &plen, &inner)) return 0;
  if (plen != 50 || inner != 0x17) return 0;
  for (i = 0; i < 50; i++) diff |= (uint32_t)(plain[i] ^ payload[i]);
  if (diff) return 0;
  /* One ciphertext byte flipped must be refused. The published record is
     restored first, because OPEN just overwrote it with its plaintext. */
  for (i = 0; i < 72; i++) record[i] = expect[i];
  record[10] = (uint8_t)(record[10] ^ 1);
  if (unprotect(key, iv, 0, record, 72, plain, &plen, &inner)) return 0;
  return 1;
}
