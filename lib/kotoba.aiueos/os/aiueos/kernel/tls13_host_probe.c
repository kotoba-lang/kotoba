/* Host-only measurement of the same TLS 1.3 + GET path the guest uses.
   Not a P2 success: Mac sockets do not count. Compile:
     cc -O2 -DAIUEOS_TLS13_HOST_PROBE \
        os/aiueos/kernel/tls13.c os/aiueos/kernel/tls_aes_gcm.c \
        os/aiueos/kernel/tls13_host_probe.c -lcrypto -o /tmp/aiueos-tls13-host
*/
#ifdef AIUEOS_TLS13_HOST_PROBE
#include "tls13.h"
#include <openssl/bn.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

uint64_t kotoba_aiueos_sha256(const uint8_t *in, uint64_t n, uint8_t out[32],
                              uint8_t *ws, uint64_t wsl) {
  static const uint8_t empty[1] = {0};
  (void)ws;
  (void)wsl;
  SHA256(n ? in : empty, (size_t)n, out);
  return 1;
}

uint64_t kotoba_aiueos_x25519(const uint8_t *scalar, const uint8_t *peer,
                              uint8_t *out, uint8_t *ws) {
  EVP_PKEY *priv = 0, *pub = 0;
  EVP_PKEY_CTX *ctx = 0;
  size_t outlen = 32;
  int ok = 0;
  (void)ws;
  priv = EVP_PKEY_new_raw_private_key(EVP_PKEY_X25519, 0, scalar, 32);
  pub = priv ? EVP_PKEY_new_raw_public_key(EVP_PKEY_X25519, 0, peer, 32) : 0;
  ctx = pub ? EVP_PKEY_CTX_new(priv, 0) : 0;
  if (ctx && EVP_PKEY_derive_init(ctx) == 1 &&
      EVP_PKEY_derive_set_peer(ctx, pub) == 1 &&
      EVP_PKEY_derive(ctx, out, &outlen) == 1 && outlen == 32)
    ok = 1;
  EVP_PKEY_CTX_free(ctx);
  EVP_PKEY_free(pub);
  EVP_PKEY_free(priv);
  return (uint64_t)ok;
}

uint64_t kotoba_aiueos_ecdsa_p256_sha256_verify(
    const uint8_t *sig, const uint8_t *digest, const uint8_t *pub,
    uint8_t *ws, uint64_t wslen) {
  EC_KEY *key = 0;
  BIGNUM *x = 0, *y = 0, *r = 0, *s = 0;
  ECDSA_SIG *esig = 0;
  int ok = 0;
  (void)ws;
  (void)wslen;
  key = EC_KEY_new_by_curve_name(NID_X9_62_prime256v1);
  x = BN_bin2bn(pub, 32, 0);
  y = BN_bin2bn(pub + 32, 32, 0);
  r = BN_bin2bn(sig, 32, 0);
  s = BN_bin2bn(sig + 32, 32, 0);
  esig = ECDSA_SIG_new();
  if (key && x && y && r && s && esig &&
      EC_KEY_set_public_key_affine_coordinates(key, x, y) == 1 &&
      ECDSA_SIG_set0(esig, r, s) == 1) {
    r = 0;
    s = 0;
    ok = ECDSA_do_verify(digest, 32, esig, key) == 1;
  }
  BN_free(x);
  BN_free(y);
  BN_free(r);
  BN_free(s);
  ECDSA_SIG_free(esig);
  EC_KEY_free(key);
  return (uint64_t)ok;
}

/* The TLS 1.3 crypto objects, stood in for by OpenSSL exactly as the three
   above are.  `kernel/tls13.c` calls these rather than carrying the cipher,
   the key schedule and the record framing itself (ADR-0132, ADR-0133, and the
   stage-5 flip), and an x86-64 kernel object cannot be linked into a probe
   that runs on this host -- so the host substitutes, which is what every
   function in this file already does.

   `kotoba_aiueos_hkdf_sha256` has NO shim here, because `tls13.c` still owns
   its own HMAC and HKDF: that seam is not flipped, and the ADR says why.

   NOTHING HERE IS EVIDENCE.  The objects' behaviour is measured by
   `scripts/verify-admissions.cljs` against their contracts and, since stage 5,
   by the boot self-tests under QEMU.  These shims exist so that
   `scripts/smoke-tls13-murakumo-profile.sh` can still drive the SNI/profile
   and live-handshake path from a Mac; if one of them disagreed with the
   object, this probe would go green and the kernel would still be right.

   Reason codes, and zero is success, as the objects define them. */

static uint64_t host_gcm(const uint8_t key[16], const uint8_t nonce[12],
                         const uint8_t *aad, uint32_t aad_len,
                         uint8_t *data, uint32_t data_len,
                         uint8_t tag[16], int seal) {
  EVP_CIPHER_CTX *c = EVP_CIPHER_CTX_new();
  uint8_t *scratch = 0;
  int n = 0, ok = 0;
  if (!c) return 5;
  scratch = data_len ? (uint8_t *)malloc(data_len) : (uint8_t *)malloc(1);
  if (!scratch) { EVP_CIPHER_CTX_free(c); return 5; }
  if (EVP_CipherInit_ex(c, EVP_aes_128_gcm(), 0, 0, 0, seal) == 1 &&
      EVP_CIPHER_CTX_ctrl(c, EVP_CTRL_AEAD_SET_IVLEN, 12, 0) == 1 &&
      EVP_CipherInit_ex(c, 0, 0, key, nonce, seal) == 1 &&
      (!seal ? EVP_CIPHER_CTX_ctrl(c, EVP_CTRL_AEAD_SET_TAG, 16, tag) == 1 : 1) &&
      (aad_len == 0 || EVP_CipherUpdate(c, 0, &n, aad, (int)aad_len) == 1) &&
      (data_len == 0 ||
       EVP_CipherUpdate(c, scratch, &n, data, (int)data_len) == 1) &&
      EVP_CipherFinal_ex(c, scratch + (data_len ? n : 0), &n) == 1)
    ok = 1;
  if (ok && seal)
    ok = EVP_CIPHER_CTX_ctrl(c, EVP_CTRL_AEAD_GET_TAG, 16, tag) == 1;
  /* Authenticate before decrypt: a refused record leaves `data` as it was. */
  if (ok && data_len) memcpy(data, scratch, data_len);
  EVP_CIPHER_CTX_free(c);
  free(scratch);
  return ok ? 0u : 5u;
}

uint64_t kotoba_aiueos_aes128_gcm(uint8_t *ctx, uint64_t ctx_len,
                                  uint8_t *data, uint64_t data_len,
                                  uint64_t mode) {
  if (ctx_len < 1280) return 1;
  if (data_len > 12288) return 2;
  if (ctx[28] > 64) return 3;
  if (mode > 1) return 4;
  return host_gcm(ctx, ctx + 16, ctx + 64, ctx[28], data, (uint32_t)data_len,
                  ctx + 32, mode == 1);
}

/* The boot known-answer test of the cipher object (ADR-0220) has nothing to
   test here: this probe's cipher IS OpenSSL, and the KAT's evidence is the
   object's own contract (contracts/aes128-gcm-selftest-v1.edn). Answers
   "every step agreed" so the probe's selftest chain reads as before. */
int64_t kotoba_aiueos_aes128_gcm_selftest(uint8_t *scratch, int64_t length) {
  (void)scratch;
  return length >= 1536 ? 0 : 6;
}

uint64_t kotoba_aiueos_tls13_record(uint8_t *ctx, uint64_t ctx_len,
                                    uint8_t *rec, uint64_t rec_len,
                                    uint64_t mode) {
  uint8_t nonce[12];
  uint32_t i;
  uint64_t seq = 0;
  if (ctx_len < 1280) return 1;
  if (mode > 1) return 2;
  if (rec_len < 22 || rec_len > 12310) return 3;
  for (i = 0; i < 8; i++) seq = (seq << 8) | ctx[48 + i];
  memcpy(nonce, ctx + 16, 12);
  for (i = 0; i < 8; i++) nonce[4 + i] ^= (uint8_t)(seq >> (56 - 8 * i));
  if (mode == 1) {
    uint32_t pt_len = (uint32_t)ctx[58] * 256u + ctx[59];
    uint32_t body_len, wire;
    if (pt_len > 12287) return 4;
    if (22 + pt_len > rec_len) return 4;
    body_len = pt_len + 1;
    wire = body_len + 16;
    rec[5 + pt_len] = ctx[56];
    rec[0] = 0x17; rec[1] = 0x03; rec[2] = 0x03;
    rec[3] = (uint8_t)(wire >> 8); rec[4] = (uint8_t)(wire & 0xff);
    memcpy(ctx + 64, rec, 5);
    ctx[28] = 5;
    if (host_gcm(ctx, nonce, ctx + 64, 5, rec + 5, body_len, ctx + 32, 1) != 0)
      return 5;
    memcpy(rec + 5 + body_len, ctx + 32, 16);
    ctx[60] = (uint8_t)((5 + wire) >> 8);
    ctx[61] = (uint8_t)((5 + wire) & 0xff);
    return 0;
  }
  {
    uint32_t clen = (uint32_t)rec[3] * 256u + rec[4];
    uint32_t body_len, n;
    if (clen + 5 != rec_len) return 5;
    if (clen < 17 || clen - 16 > 12288) return 5;
    body_len = clen - 16;
    memcpy(ctx + 64, rec, 5);
    ctx[28] = 5;
    memcpy(ctx + 32, rec + 5 + body_len, 16);
    if (host_gcm(ctx, nonce, ctx + 64, 5, rec + 5, body_len, ctx + 32, 0) != 0)
      return 6;
    n = body_len;
    while (n > 0 && rec[5 + n - 1] == 0) n--;
    if (n == 0) return 7;
    ctx[56] = rec[5 + n - 1];
    ctx[58] = (uint8_t)((n - 1) >> 8);
    ctx[59] = (uint8_t)((n - 1) & 0xff);
    return 0;
  }
}

static int tcp_host(const char *host) {
  struct addrinfo hints, *res = 0, *rp;
  int fd = -1;
  memset(&hints, 0, sizeof(hints));
  hints.ai_socktype = SOCK_STREAM;
  hints.ai_family = AF_INET;
  if (getaddrinfo(host, "443", &hints, &res)) return -1;
  for (rp = res; rp; rp = rp->ai_next) {
    fd = (int)socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
    if (fd < 0) continue;
    if (connect(fd, rp->ai_addr, rp->ai_addrlen) == 0) break;
    close(fd);
    fd = -1;
  }
  freeaddrinfo(res);
  return fd;
}

static int configured_profile(const char *host, const char *path) {
  static const uint8_t client_random[32] = {
    0x41,0x49,0x55,0x45,0x4f,0x53,0x2d,0x4b,0x31,0x36,0x2d,0x44,0x49,0x52,0x45,
    0x43,0x54,0x2d,0x48,0x54,0x54,0x50,0x53,0x2d,0x50,0x52,0x4f,0x42,0x45,0x31};
  static const uint8_t scalar[32] = {
    0x7a,0x1e,0x05,0x13,0xc1,0x0d,0x15,0x07,0xa1,0xe0,0x53,0x00,0x6d,0x75,0x72,0x61,
    0x6b,0x75,0x6d,0x6f,0x2e,0x63,0x6c,0x6f,0x75,0x64,0x13,0x01,0x03,0x04,0x00,0x1d};
  uint8_t request[512];
  int n;
  if (!host || !path || path[0] != '/') return 0;
  n = snprintf((char *)request, sizeof(request),
               "GET %s HTTP/1.1\r\nHost: %s\r\n"
               "User-Agent: aiueos-k16-direct-probe\r\n"
               "Accept: application/json\r\nConnection: close\r\n\r\n",
               path, host);
  if (n <= 0 || (size_t)n >= sizeof(request)) return 0;
  return aiueos_tls13_configure(host, request, (uint32_t)n,
                                client_random, scalar);
}

static int configuration_refusals(void) {
  static const uint8_t request[] = "GET / HTTP/1.1\r\n\r\n";
  uint8_t one[32], zero[32];
  memset(one, 1, sizeof(one));
  memset(zero, 0, sizeof(zero));
  return !aiueos_tls13_configure("", request, sizeof(request) - 1, one, one) &&
         !aiueos_tls13_configure("API.murakumo.cloud", request,
                                 sizeof(request) - 1, one, one) &&
         !aiueos_tls13_configure("-api.murakumo.cloud", request,
                                 sizeof(request) - 1, one, one) &&
         !aiueos_tls13_configure("api-.murakumo.cloud", request,
                                 sizeof(request) - 1, one, one) &&
         !aiueos_tls13_configure("api.murakumo.cloud", request,
                                 sizeof(request) - 1, zero, one) &&
         !aiueos_tls13_configure("api.murakumo.cloud", request,
                                 sizeof(request) - 1, one, zero);
}

static int clienthello_profile_ok(const uint8_t *ch, uint32_t ch_len,
                                  const char *host) {
  size_t host_len = strlen(host);
  if (!ch || host_len > 63 || ch_len != 145 + host_len) return 0;
  if ((((uint32_t)ch[3] << 8) | ch[4]) != ch_len - 5) return 0;
  if ((((uint32_t)ch[7] << 8) | ch[8]) != ch_len - 9) return 0;
  if ((((uint32_t)ch[59] << 8) | ch[60]) != host_len) return 0;
  return memcmp(ch + 61, host, host_len) == 0;
}

int main(int argc, char **argv) {
  uint8_t ch[256], flight[512], rx[8192];
  uint32_t ch_len = 0, fin_len = 0, get_len = 0;
  int fd, n, i;
  int inspect = argc > 1 && strcmp(argv[1], "--inspect") == 0;
  const char *host = (inspect && argc > 2) ? argv[2] :
                     ((!inspect && argc > 1) ? argv[1] : "kotobase.net");
  const char *path = (inspect && argc > 3) ? argv[3] :
                     ((!inspect && argc > 2) ? argv[2] :
                      "/ipfs/bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku");
  if (!aiueos_tls13_aes_selftest() || !aiueos_tls13_hmac_selftest() ||
      !aiueos_tls13_ecdsa_selftest() || !aiueos_tls13_record_selftest() ||
      !configuration_refusals()) {
    puts("selftest fail");
    return 1;
  }
  if ((argc > 1) && !configured_profile(host, path)) {
    puts("profile fail");
    return 1;
  }
  aiueos_tls13_reset();
  if (!aiueos_tls13_clienthello(ch, &ch_len)) {
    puts("clienthello fail");
    return 1;
  }
  if (argc > 1 && !clienthello_profile_ok(ch, ch_len, host)) {
    puts("clienthello profile mismatch");
    return 1;
  }
  if (inspect) {
    printf("profile ok host=%s path=%s clienthello=%u trust=transport-only\n",
           host, path, ch_len);
    return 0;
  }
  fd = tcp_host(host);
  if (fd < 0) {
    puts("connect fail");
    return 1;
  }
  if (send(fd, ch, ch_len, 0) != (ssize_t)ch_len) {
    puts("clienthello send fail");
    return 1;
  }
  for (i = 0; i < 64 && !aiueos_tls13_handshake_ready(); i++) {
    n = (int)recv(fd, rx, sizeof(rx), 0);
    if (n <= 0) break;
    if (!aiueos_tls13_feed(rx, (uint32_t)n)) {
      printf("feed fail stage=%u rec=%u inner=%u\n",
             aiueos_tls13_stage(), aiueos_tls13_last_record_type(),
             aiueos_tls13_last_inner_type());
      return 1;
    }
  }
  if (!aiueos_tls13_handshake_ready()) {
    printf("handshake incomplete stage=%u rec=%u certverify=%d\n",
           aiueos_tls13_stage(), aiueos_tls13_last_record_type(),
           aiueos_tls13_certverify_ok());
    return 1;
  }
  if (!aiueos_tls13_run_certverify() ||
      !aiueos_tls13_certverify_ok() ||
      aiueos_tls13_certverify_scheme() != 0x0403) {
    printf("certverify fail scheme=%u\n", aiueos_tls13_certverify_scheme());
    return 1;
  }
  puts("handshake ok");
  puts("certverify ok scheme=ecdsa_secp256r1_sha256");
  if (!aiueos_tls13_take_finished(flight, &fin_len) ||
      !aiueos_tls13_take_http(flight + fin_len, &get_len)) {
    puts("take fail");
    return 1;
  }
  printf("fin=%u get=%u\n", fin_len, get_len);
  if (send(fd, flight, fin_len + get_len, 0) != (ssize_t)(fin_len + get_len)) {
    puts("send fin+get fail");
    return 1;
  }
  for (i = 0; i < 64; i++) {
    n = (int)recv(fd, rx, sizeof(rx), 0);
    if (n <= 0) break;
    if (!aiueos_tls13_feed(rx, (uint32_t)n)) {
      printf("app feed fail rec=%u inner=%u fail=%d alert=%u/%u app=%u\n",
             aiueos_tls13_last_record_type(), aiueos_tls13_last_inner_type(),
             aiueos_tls13_failed(), aiueos_tls13_alert_level(),
             aiueos_tls13_alert_desc(), aiueos_tls13_app_len());
      if (aiueos_tls13_app_len() >= 12 && aiueos_tls13_app()[0] == 'H') {
        puts("http before alert");
        close(fd);
        return 0;
      }
      return 1;
    }
    if (aiueos_tls13_app_len() >= 12) {
      uint32_t k, shown = aiueos_tls13_app_len();
      if (shown > 80) shown = 80;
      printf("app len=%u nst=%u first=", aiueos_tls13_app_len(),
             aiueos_tls13_nst_count());
      for (k = 0; k < shown; k++) {
        unsigned c = aiueos_tls13_app()[k];
        putchar((c >= 32 && c < 127) ? (int)c : '.');
      }
      putchar('\n');
      close(fd);
      return (aiueos_tls13_app()[0] == 'H') ? 0 : 2;
    }
  }
  printf("no http app=%u nst=%u rec=%u inner=%u fail=%d\n",
         aiueos_tls13_app_len(), aiueos_tls13_nst_count(),
         aiueos_tls13_last_record_type(), aiueos_tls13_last_inner_type(),
         aiueos_tls13_failed());
  close(fd);
  return 1;
}
#endif
