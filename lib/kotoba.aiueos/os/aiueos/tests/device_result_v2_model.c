#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../kernel/device_result.h"

static char signed_text[1024];
static uint32_t signed_length;

int aiueos_device_test_random_bytes(uint8_t *out, uint32_t bytes) {
  for (uint32_t i = 0; i < bytes; i++) out[i] = 0x02;
  return 1;
}

int aiueos_device_p256_key_load(uint8_t key[32]) {
  memset(key, 0, 32);
  key[31] = 1;
  return 1;
}

int aiueos_device_p256_key_save(const uint8_t key[32]) {
  (void)key;
  return 0;
}

uint64_t kotoba_aiueos_sha256(const uint8_t *input, uint64_t bytes,
                              uint8_t digest[32], uint8_t *workspace,
                              uint64_t workspace_bytes) {
  (void)workspace;
  (void)workspace_bytes;
  if (bytes >= sizeof(signed_text)) return 0;
  memcpy(signed_text, input, (size_t)bytes);
  signed_text[bytes] = 0;
  signed_length = (uint32_t)bytes;
  memset(digest, 0x33, 32);
  return 1;
}

uint64_t kotoba_aiueos_ecdsa_p256_sign(const uint8_t *in,
                                       uint64_t in_length,
                                       uint8_t *signature,
                                       uint64_t signature_length,
                                       uint8_t *workspace, uint64_t workspace_length) {
  (void)in;
  (void)in_length;
  (void)signature_length;
  (void)workspace; (void)workspace_length;
  memset(signature, 0x55, 64);
  return 1;
}

uint64_t kotoba_aiueos_ecdsa_p256_public(const uint8_t *private_key, uint64_t private_key_length,
                                         uint8_t *public_key, uint64_t public_key_length,
                                         uint8_t *workspace, uint64_t workspace_length) {
  (void)private_key; (void)private_key_length; (void)public_key_length;
  (void)workspace; (void)workspace_length;
  memset(public_key, 0x01, 64);
  return 1;
}

/* The C writer this model's kernel counterpart deleted, kept HERE as the
   protocol 2 oracle.  `device_result.c` now calls
   `kotoba_aiueos_device_worker_canonical` and this host build has no x86-64
   Kotoba object to link, so the model supplies the symbol -- and supplying it
   with the OLD field-by-field writer is what makes this test a parity check
   rather than a stub: it proves the 576-byte context `device_result.c` fills
   denotes the same text the C used to write from the same struct.

   The bytes it produces are also where
   `contracts/device-worker-canonical-v1.edn`'s protocol 2 vectors come from,
   so the Kotoba object is pinned against exactly this function's output.

   Protocol 3 is deliberately absent: the C never built a v3 canonical text, so
   there is nothing here that could be its oracle.  The object's v3 rows are
   graded against the server's own worked example instead. */
static uint64_t ctx_number_at(const uint8_t *ctx, uint32_t offset) {
  uint64_t value = 0;
  for (uint32_t i = 0; i < 8; i++) value = (value << 8) | ctx[offset + i];
  return value;
}

static uint32_t oracle_put(uint8_t *out, uint32_t at, const char *text) {
  while (*text) out[at++] = (uint8_t)*text++;
  return at;
}

static uint32_t oracle_decimal(uint8_t *out, uint32_t at, uint64_t value) {
  char digits[24];
  uint32_t n = 0;
  do { digits[n++] = (char)('0' + value % 10U); value /= 10U; } while (value);
  while (n) out[at++] = (uint8_t)digits[--n];
  return at;
}

static uint32_t oracle_text_field(uint8_t *out, uint32_t at, const uint8_t *ctx,
                                  uint32_t offset, uint32_t bytes) {
  out[at++] = '\n';
  for (uint32_t i = 0; i < bytes; i++) out[at++] = ctx[offset + i];
  return at;
}

static uint32_t oracle_number_field(uint8_t *out, uint32_t at,
                                    const uint8_t *ctx, uint32_t offset) {
  out[at++] = '\n';
  return oracle_decimal(out, at, ctx_number_at(ctx, offset));
}

/* kotoba/p256-did.kotoba on the host (JUN-554): the C it replaced, behind the object's interface. The object itself is
   compared with that C under QEMU by scripts/p256-did-diff. */
int64_t kotoba_aiueos_p256_did(const uint8_t *pub, uint64_t pub_len, char *out, uint64_t cap) {
  static const char alphabet[] = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  uint8_t mk[35], digits[64] = {0};
  uint32_t dc = 1, lead = 0, at = 0, j, i;
  char text[96];
  if (!out || (pub_len >> 32) || (cap >> 32) || pub_len != 64) return 0;
  mk[0] = 0x80; mk[1] = 0x24; mk[2] = (pub[63] & 1U) ? 0x03 : 0x02;
  for (i = 0; i < 32; i++) mk[3 + i] = pub[i];
  for (j = 0; j < 35; j++) {
    uint32_t carry = mk[j];
    for (i = 0; i < dc; i++) { uint32_t v = (uint32_t)digits[i] * 256U + carry; digits[i] = (uint8_t)(v % 58U); carry = v / 58U; }
    while (carry) { if (dc >= 64) return 0; digits[dc++] = (uint8_t)(carry % 58U); carry /= 58U; }
  }
  while (lead < 35 && !mk[lead]) lead++;
  if (lead + dc + 1 > 64) return 0;
  for (i = 0; i < 9; i++) text[at++] = "did:key:z"[i];
  for (i = 0; i < lead; i++) text[at++] = '1';
  while (dc) text[at++] = alphabet[digits[--dc]];
  text[at++] = 0;
  for (i = 0; i < at && i < cap; i++) out[i] = text[i];
  return at <= cap;
}

/* kotoba/device-result-text.kotoba on the host (JUN-554): the C text it replaced, behind the object's interface. The
   object itself is compared with that C under QEMU by scripts/device-result-text-diff. */
static int64_t drt_put(uint8_t *o, uint64_t cap, int64_t at, const char *t) {
  for (uint64_t i = 0; t[i]; i++) { if (at < 0 || (uint64_t)at >= cap) return -1; o[at++] = (uint8_t)t[i]; }
  return at;
}
static int64_t drt_hex(uint8_t *o, uint64_t cap, int64_t at, const uint8_t *in, uint32_t n) {
  static const char h[] = "0123456789abcdef";
  for (uint32_t i = 0; i < n; i++) { char two[3] = {h[in[i] >> 4], h[in[i] & 15], 0}; at = drt_put(o, cap, at, two); }
  return at;
}
static int64_t drt_dec(uint8_t *o, uint64_t cap, int64_t at, uint64_t v) {
  char d[21]; int n = 0; d[20] = 0;
  do { d[19 - n++] = (char)('0' + v % 10); v /= 10; } while (v);
  return drt_put(o, cap, at, d + 20 - n);
}
static uint64_t drt_num(const uint8_t *r, int k) { uint64_t v = 0; for (int i = 0; i < 8; i++) v = v << 8 | r[192 + k * 8 + i]; return v; }
int64_t kotoba_aiueos_device_result_text(const uint8_t *r, uint64_t rn, uint64_t mode, uint8_t *o, uint64_t cap) {
  static const char *names[] = {"token", "second-token", "generated-tokens", "decode-tokens", "model-load-cycles",
    "first-token-cycles", "decode-cycles", "inference-cycles", "vector-bits", "worker-threads", "tsc-hz"};
  int64_t at;
  if (!o || !r || (rn >> 32) || (cap >> 32) || rn < 288 || rn > 512 || cap > 16384 || mode > 1) return 0;
  if (mode == 0) {
    at = drt_hex(o, cap, drt_put(o, cap, drt_put(o, cap, 0, "aiueos-k16-result-v2"), "\naiueos-k16-"), r, 6);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\n"), r + 8, 64);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\n"), r + 72, 8);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\n"), r + 80, 32);
    at = drt_put(o, cap, at, "\nQwen3.8-27B-UD-IQ3_XXS.gguf\n2");
    for (int k = 0; k < 11; k++) at = drt_dec(o, cap, drt_put(o, cap, at, "\n"), drt_num(r, k));
    at = drt_hex(o, cap, drt_put(o, cap, at, "\n"), r + 112, 16);
  } else {
    at = drt_hex(o, cap, drt_put(o, cap, 0, "{\"node\":\"aiueos-k16-"), r, 6);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\",\"public-key\":\""), r + 8, 64);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\",\"boot\":\""), r + 72, 8);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\",\"model-sha256\":\""), r + 80, 32);
    at = drt_dec(o, cap, drt_put(o, cap, at, "\",\"model\":\"Qwen3.8-27B-UD-IQ3_XXS.gguf\",\"protocol\":2,\"token\":"), drt_num(r, 0));
    for (int k = 1; k < 11; k++) {
      char key[32]; int n = 0; key[n++] = ','; key[n++] = '"';
      for (const char *c = names[k]; *c; c++) key[n++] = *c;
      key[n++] = '"'; key[n++] = ':'; key[n] = 0;
      at = drt_dec(o, cap, drt_put(o, cap, at, key), drt_num(r, k));
    }
    at = drt_hex(o, cap, drt_put(o, cap, at, ",\"nonce\":\""), r + 112, 16);
    at = drt_hex(o, cap, drt_put(o, cap, at, "\",\"signature\":\""), r + 128, 64);
    at = drt_put(o, cap, at, "\"}");
  }
  return at < 0 ? 0 : at;
}

int64_t kotoba_aiueos_device_worker_canonical(uint8_t *ctx, uint64_t ctx_len,
                                              uint8_t *out, uint64_t out_cap) {
  if (ctx_len < 576) return -1;
  if (out_cap < 1024) return -2;
  if (ctx[0] != 2) return -3;               /* this oracle is v2 only */
  if (ctx[1] < 1 || ctx[1] > 3) return -4;
  if (ctx[2] != 0) return -5;
  if (ctx_number_at(ctx, 104) != 0) return -7;
  uint32_t at = oracle_put(out, 0, "aiueos-k16-worker-v2");
  at = oracle_text_field(out, at, ctx, 128, 23);
  at = oracle_text_field(out, at, ctx, 160, 128);
  at = oracle_text_field(out, at, ctx, 288, 16);
  at = oracle_text_field(out, at, ctx, 304, 64);
  at = oracle_number_field(out, at, ctx, 8);
  out[at++] = '\n';
  at = oracle_put(out, at, ctx[1] == 1 ? "poll"
                           : (ctx[1] == 2 ? "result" : "control-ack"));
  out[at++] = '\n';
  if (ctx[1] == 1) out[at++] = '-';
  else at = oracle_decimal(out, at, ctx_number_at(ctx, 16));
  out[at++] = '\n';
  out[at++] = '2';
  at = oracle_number_field(out, at, ctx, 24);
  at = oracle_number_field(out, at, ctx, 32);
  at = oracle_number_field(out, at, ctx, 40);
  at = oracle_number_field(out, at, ctx, 48);
  at = oracle_number_field(out, at, ctx, 56);
  at = oracle_number_field(out, at, ctx, 64);
  at = oracle_number_field(out, at, ctx, 72);
  at = oracle_number_field(out, at, ctx, 80);
  at = oracle_number_field(out, at, ctx, 88);
  at = oracle_number_field(out, at, ctx, 96);
  at = oracle_text_field(out, at, ctx, 496, 32);
  return (int64_t)at;
}

static int contains(const uint8_t *request, uint32_t length,
                    const char *needle) {
  size_t n = strlen(needle);
  if (!n || n > length) return 0;
  for (uint32_t i = 0; i + n <= length; i++)
    if (!memcmp(request + i, needle, n)) return 1;
  return 0;
}

#define CHECK(x) do { if (!(x)) { \
  fprintf(stderr, "check failed: %s\n", #x); return 1; \
} } while (0)

/* The canonical text this file already captures through the `kotoba_aiueos_sha256`
   stub is the ORACLE for `os/aiueos/kotoba/device-worker-canonical.kotoba`.
   Printed here rather than transcribed into that object's contract by hand:
   the contract pins the bytes the C produces, and a transcription is a second
   thing that has to agree about what they are. */
static void emit(const char *label) {
  printf("%s\t%u\t", label, signed_length);
  for (uint32_t i = 0; i < signed_length; i++)
    printf("%02x", (unsigned char)signed_text[i]);
  printf("\n");
}

int main(int argc, char **argv) {
  const int dump = argc > 1 && !strcmp(argv[1], "--dump-canonical");
  struct aiueos_boot_info boot = {
    .magic = AIUEOS_BOOT_INFO_MAGIC,
    .version = AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED,
    .model_load_cycles = 8000000000ULL,
    .tsc_hz = 4000000000ULL
  };
  memset(boot.model_sha256, 0xaa, sizeof(boot.model_sha256));
  const uint8_t mac[6] = {0x70, 0x70, 0xfc, 0x0b, 0xb6, 0x32};
  uint8_t request[1024];
  char did[96];

  struct aiueos_device_result result = {
    .boot = &boot, .mac = mac, .token = 2005, .second_token = 17,
    .generated_tokens = 8, .decode_tokens = 7,
    .first_token_cycles = 12000000000ULL,
    .decode_cycles = 56000000000ULL,
    .inference_cycles = 68000000000ULL,
    .vector_bits = 256, .worker_threads = 2
  };
  uint32_t length = aiueos_device_result_http_request(
    &result, request, sizeof(request), did, sizeof(did));
  if (!length) fprintf(stderr, "result request refused signed-length=%u\n",
                       signed_length);
  CHECK(length && signed_length);
  CHECK(!strncmp(signed_text, "aiueos-k16-result-v2\n", 21));
  CHECK(strstr(signed_text,
    "\nQwen3.8-27B-UD-IQ3_XXS.gguf\n2\n2005\n17\n8\n7\n"
    "8000000000\n12000000000\n56000000000\n68000000000\n"
    "256\n2\n4000000000\n"));
  CHECK(contains(request, length, "\"protocol\":2"));
  CHECK(contains(request, length, "\"decode-tokens\":7"));
  CHECK(contains(request, length, "\"decode-cycles\":56000000000"));
  CHECK(contains(request, length, "User-Agent: aiueos-k16-node-v2"));

  struct aiueos_device_worker_request worker = {
    .boot = &boot, .mac = mac, .sequence = 7,
    .operation = AIUEOS_DEVICE_WORKER_RESULT, .job_id = 42,
    .token = 2005, .second_token = 17,
    .generated_tokens = 8, .decode_tokens = 7,
    .first_token_cycles = 12000000000ULL,
    .decode_cycles = 56000000000ULL,
    .inference_cycles = 68000000000ULL,
    .vector_bits = 256, .worker_threads = 2
  };
  length = aiueos_device_worker_http_request(
    &worker, request, sizeof(request), did, sizeof(did));
  CHECK(length && !strncmp(signed_text, "aiueos-k16-worker-v2\n", 21));
  CHECK(strstr(signed_text,
    "\n7\nresult\n42\n2\n2005\n17\n8\n7\n"
    "12000000000\n56000000000\n68000000000\n256\n2\n4000000000\n"));
  CHECK(contains(request, length, "User-Agent: aiueos-k16-worker-v2"));
  if (dump) emit("worker-result-v2");

  worker = (struct aiueos_device_worker_request){
    .boot = &boot, .mac = mac, .sequence = 8,
    .operation = AIUEOS_DEVICE_WORKER_POLL
  };
  length = aiueos_device_worker_http_request(
    &worker, request, sizeof(request), did, sizeof(did));
  CHECK(length && strstr(signed_text,
    "\n8\npoll\n-\n2\n0\n0\n0\n0\n0\n0\n0\n0\n0\n4000000000\n"));
  if (dump) emit("worker-poll-v2");

  worker = (struct aiueos_device_worker_request){
    .boot = &boot, .mac = mac, .sequence = 9,
    .operation = AIUEOS_DEVICE_WORKER_CONTROL_ACK, .job_id = 1788078031098390ULL
  };
  length = aiueos_device_worker_http_request(
    &worker, request, sizeof(request), did, sizeof(did));
  CHECK(length && strstr(signed_text,
    "\n9\ncontrol-ack\n1788078031098390\n2\n0\n0\n0\n0\n0\n0\n0\n0\n0\n4000000000\n"));
  if (dump) emit("worker-control-ack-v2");

  worker = (struct aiueos_device_worker_request){
    .boot = &boot, .mac = mac, .sequence = 12,
    .operation = AIUEOS_DEVICE_WORKER_RESULT, .job_id = 1788078031098390ULL,
    .token = 2005, .second_token = 17,
    .generated_tokens = 3, .decode_tokens = 2,
    .first_token_cycles = 12000000000ULL,
    .decode_cycles = 24000000000ULL,
    .inference_cycles = 36000000000ULL,
    .vector_bits = 256, .worker_threads = 2
  };
  length = aiueos_device_worker_http_request(
    &worker, request, sizeof(request), did, sizeof(did));
  CHECK(length);
  if (dump) emit("worker-result-v2-spec-shaped");

  puts("AIUEOS_DEVICE_RESULT_V2_OK signed=decode-boundary backward-server=v1+v2");
  return 0;
}
