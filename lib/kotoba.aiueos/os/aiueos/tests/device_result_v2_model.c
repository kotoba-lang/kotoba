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

uint64_t kotoba_aiueos_ecdsa_p256_sign(const uint8_t *private_key,
                                       const uint8_t *digest,
                                       const uint8_t *nonce,
                                       uint8_t *signature,
                                       uint8_t *workspace) {
  (void)private_key;
  (void)digest;
  (void)nonce;
  (void)workspace;
  memset(signature, 0x55, 64);
  return 1;
}

uint64_t kotoba_aiueos_ecdsa_p256_public(const uint8_t *private_key,
                                         uint8_t *public_key,
                                         uint8_t *workspace) {
  (void)private_key;
  (void)workspace;
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
