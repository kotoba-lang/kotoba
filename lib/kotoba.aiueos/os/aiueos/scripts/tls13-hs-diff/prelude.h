/* The state and the callees of kernel/tls13.c's handshake state machine, for scripts/tls13-hs-diff. Each callee logs
   itself into a trace and takes its result from a script both versions share, and mutates the state the way the real
   one does on success (parse_serverhello sets have_sh / have_hs_keys, verify_certificate_verify certverify_parsed, ...).
   unprotect "opens" a record as inner type rec[5] and plaintext rec[6..). */
#include <stdint.h>
#define aiueos_tls13_feed PFX(feed)
#define TLS_TR_MAX 12288
#define TLS_RX_MAX 12288
#define TLS_APP_MAX 4096
#define TLS_HS_MAX 12288
#define TLS_SCRATCH
extern int64_t kotoba_aiueos_tls13_hs_step(const uint8_t *, uint64_t, uint64_t);
extern int64_t kotoba_aiueos_tls13_record_step(const uint8_t *, uint64_t, uint64_t);
extern int64_t kotoba_aiueos_tls13_inner_step(const uint8_t *, uint64_t, uint64_t, uint64_t);
static uint8_t transcript[TLS_TR_MAX]; static uint32_t transcript_len;
static uint8_t rx[TLS_RX_MAX]; static uint32_t rx_len;
static uint8_t hs_partial[TLS_HS_MAX]; static uint32_t hs_partial_len;
static uint8_t app_buf[TLS_APP_MAX]; static uint32_t app_len;
static uint8_t s_hs_key[16], s_hs_iv[12], s_ap_key[16], s_ap_iv[12];
static uint64_t s_hs_seq, s_ap_seq;
static int saw_record, have_sh, have_hs_keys, have_server_finished, handshake_ready, failed, certverify_parsed, have_leaf_pub;
static uint8_t first_record_type, last_record_type, last_inner_type;
static uint64_t trace; static uint32_t calls, script;
static void note(uint32_t op, uint32_t a, uint32_t b) { calls++; trace = (trace ^ (op * 0x9e3779b9u + a * 31u + b)) * 0x100000001b3ull; }
static int scripted(void) { uint32_t bit = (script >> (calls % 29)) & 1; return !(bit && (calls % 7) == 3); }
static uint16_t be16(const uint8_t *p) { return (uint16_t)(((uint32_t)p[0] << 8) | p[1]); }
static uint32_t be24(const uint8_t *p) { return ((uint32_t)p[0] << 16) | ((uint32_t)p[1] << 8) | p[2]; }
static void copy_bytes(uint8_t *d, const uint8_t *s, uint32_t n) { uint32_t i; if (d < s) for (i = 0; i < n; i++) d[i] = s[i]; else for (i = n; i > 0; i--) d[i - 1] = s[i - 1]; }
static uint32_t sum(const uint8_t *p, uint32_t n) { uint32_t h = 2166136261u; for (uint32_t i = 0; i < n; i++) h = (h ^ p[i]) * 16777619u; return h; }
static int transcript_add(const uint8_t *p, uint32_t n) {
  note(1, n, sum(p, n));
  if (transcript_len + n > TLS_TR_MAX) return 0;
  copy_bytes(transcript + transcript_len, p, n); transcript_len += n; return 1; }
static int finish_check(const uint8_t *verify, uint32_t n) { int r = scripted(); note(2, n, sum(verify, n) + (uint32_t)r); if (r) have_server_finished = 1; return r; }
static int parse_certificate(const uint8_t *hs, uint32_t n) { int r = n >= 8 && hs[0] == 0x0b && be24(hs + 1) + 4 == n && scripted(); note(3, n, sum(hs, n) + (uint32_t)r); if (r) have_leaf_pub = 1; return r; }
static int verify_certificate_verify(const uint8_t *hs, uint32_t n) { int r = have_leaf_pub && scripted(); note(4, n, sum(hs, n) + (uint32_t)r); if (r) certverify_parsed = 1; return r; }
static int derive_ap_keys(void) { int r = scripted(); note(5, (uint32_t)r, 0); if (r) s_ap_seq = 0; return r; }
static int parse_serverhello(const uint8_t *hs, uint32_t n) { int r = scripted(); note(6, n, sum(hs, n) + (uint32_t)r); if (r) { have_sh = 1; have_hs_keys = 1; s_hs_seq = 0; } return r; }
static int unprotect(const uint8_t key[16], const uint8_t iv[12], uint64_t seq, uint8_t *rec, uint32_t rec_len,
                     uint8_t *pt, uint32_t *pt_len, uint8_t *inner_type) {
  int r = rec_len >= 6 && scripted();
  note(7, (uint32_t)seq + (key == s_ap_key ? 0x1000u : 0) + (iv == s_ap_iv ? 0x2000u : 0), rec_len + (uint32_t)r);
  if (!r) return 0;
  *inner_type = rec[5]; *pt_len = rec_len - 6; copy_bytes(pt, rec + 6, rec_len - 6); return 1; }
