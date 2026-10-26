#include <stdint.h>
#include "device_result.h"

/* 1024 rather than 512: the widest protocol 3 worker form is 716 bytes.
   os/aiueos/contracts/device-worker-canonical-v1.edn:out states the sum.
   Both come from device_result.h, which is where the boot self-test in main.c
   reads the same layout. */
#define DEVICE_CANONICAL_MAX AIUEOS_DEVICE_WORKER_CANONICAL_MAX
#define DEVICE_WORKER_CTX_BYTES AIUEOS_DEVICE_WORKER_CTX_BYTES
#define DEVICE_BODY_MAX 1024U

extern uint64_t kotoba_aiueos_sha256(
    const uint8_t *, uint64_t, uint8_t[32], uint8_t *, uint64_t);
extern uint64_t kotoba_aiueos_ecdsa_p256_sign(
    const uint8_t *, const uint8_t *, const uint8_t *, uint8_t *, uint8_t *);
extern uint64_t kotoba_aiueos_ecdsa_p256_public(
    const uint8_t *, uint8_t *, uint8_t *);
extern int aiueos_device_p256_key_load(uint8_t key[32]);
extern int aiueos_device_p256_key_save(const uint8_t key[32]);

static const uint8_t p256_order[32] = {
  0xff,0xff,0xff,0xff,0x00,0x00,0x00,0x00,
  0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
  0xbc,0xe6,0xfa,0xad,0xa7,0x17,0x9e,0x84,
  0xf3,0xb9,0xca,0xc2,0xfc,0x63,0x25,0x51
};
static const char base58_alphabet[] =
  "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
static const char hex_alphabet[] = "0123456789abcdef";
#if defined(__GNUC__) && !defined(AIUEOS_DEVICE_RESULT_TESTING)
#define AIUEOS_DEVICE_HIGH_BSS __attribute__((section(".high_bss")))
#else
#define AIUEOS_DEVICE_HIGH_BSS
#endif
/* Device signing begins only after owned paging is active.  Keep its reusable
   workspaces out of the low W^X aperture shared with admitted user pages. */
static uint8_t sha_workspace[512] AIUEOS_DEVICE_HIGH_BSS;
static uint8_t p256_workspace[2048] AIUEOS_DEVICE_HIGH_BSS;
static uint8_t device_boot_id[8];
static int device_boot_id_ready;

struct bounded_buffer {
  uint8_t *bytes;
  uint32_t length, capacity;
  int ok;
};

static void secure_zero(void *memory, uint32_t bytes) {
  volatile uint8_t *out = (volatile uint8_t *)memory;
  while (bytes--) *out++ = 0;
}

static void put_byte(struct bounded_buffer *b, uint8_t value) {
  if (!b->ok || b->length >= b->capacity) { b->ok = 0; return; }
  b->bytes[b->length++] = value;
}

static void put_text(struct bounded_buffer *b, const char *text) {
  if (!text) { b->ok = 0; return; }
  while (*text) put_byte(b, (uint8_t)*text++);
}

static void put_decimal(struct bounded_buffer *b, uint64_t value) {
  char digits[20];
  uint32_t n = 0;
  do {
    digits[n++] = (char)('0' + value % 10U);
    value /= 10U;
  } while (value && n < sizeof(digits));
  while (n) put_byte(b, (uint8_t)digits[--n]);
}

static void hex_encode(const uint8_t *in, uint32_t bytes, char *out) {
  for (uint32_t i = 0; i < bytes; i++) {
    out[i * 2] = hex_alphabet[in[i] >> 4];
    out[i * 2 + 1] = hex_alphabet[in[i] & 15U];
  }
  out[bytes * 2] = 0;
}

#ifndef AIUEOS_DEVICE_RESULT_TESTING
static void cpuid(uint32_t leaf, uint32_t subleaf,
                  uint32_t *a, uint32_t *b, uint32_t *c, uint32_t *d) {
  __asm__ volatile("cpuid"
                   : "=a"(*a), "=b"(*b), "=c"(*c), "=d"(*d)
                   : "a"(leaf), "c"(subleaf));
}

static int rdrand64(uint64_t *value) {
  for (uint32_t attempt = 0; attempt < 32; attempt++) {
    uint8_t ready;
    uint64_t candidate;
    __asm__ volatile("rdrand %0; setc %1" : "=r"(candidate), "=qm"(ready));
    if (ready) { *value = candidate; return 1; }
    __asm__ volatile("pause");
  }
  return 0;
}

int aiueos_cpu_random_bytes(uint8_t *out, uint32_t bytes) {
  uint32_t a, b, c, d;
  if (!out || !bytes) return 0;
  cpuid(1, 0, &a, &b, &c, &d);
  if (!(c & (1U << 30))) return 0;
  uint32_t offset = 0;
  while (offset < bytes) {
    uint64_t word;
    if (!rdrand64(&word)) return 0;
    for (uint32_t i = 0; i < 8 && offset < bytes; i++, offset++)
      out[offset] = (uint8_t)(word >> (i * 8));
  }
  return 1;
}
#else
extern int aiueos_device_test_random_bytes(uint8_t *, uint32_t);
int aiueos_cpu_random_bytes(uint8_t *out, uint32_t bytes) {
  return aiueos_device_test_random_bytes(out, bytes);
}
#endif

static int scalar_valid(const uint8_t scalar[32]) {
  int nonzero = 0;
  for (uint32_t i = 0; i < 32; i++) nonzero |= scalar[i];
  if (!nonzero) return 0;
  for (uint32_t i = 0; i < 32; i++) {
    if (scalar[i] < p256_order[i]) return 1;
    if (scalar[i] > p256_order[i]) return 0;
  }
  return 0;
}

static int random_scalar(uint8_t scalar[32]) {
  for (uint32_t attempt = 0; attempt < 16; attempt++)
    if (aiueos_cpu_random_bytes(scalar, 32) && scalar_valid(scalar)) return 1;
  return 0;
}

static int device_private_key(uint8_t key[32]) {
  if (aiueos_device_p256_key_load(key) && scalar_valid(key)) return 1;
  if (!random_scalar(key)) return 0;
  return aiueos_device_p256_key_save(key);
}

static int device_boot_id_refresh(void) {
  if (!aiueos_cpu_random_bytes(device_boot_id, sizeof(device_boot_id))) return 0;
  device_boot_id_ready = 1;
  return 1;
}

static int device_boot_id_ensure(void) {
  if (device_boot_id_ready) return 1;
  return device_boot_id_refresh();
}

static int base58_encode(const uint8_t *input, uint32_t input_bytes,
                         char *out, uint32_t capacity) {
  uint8_t digits[64] = {0};
  uint32_t digit_count = 1;
  for (uint32_t j = 0; j < input_bytes; j++) {
    uint32_t carry = input[j];
    for (uint32_t i = 0; i < digit_count; i++) {
      uint32_t value = (uint32_t)digits[i] * 256U + carry;
      digits[i] = (uint8_t)(value % 58U);
      carry = value / 58U;
    }
    while (carry) {
      if (digit_count >= sizeof(digits)) return 0;
      digits[digit_count++] = (uint8_t)(carry % 58U);
      carry /= 58U;
    }
  }
  uint32_t leading = 0;
  while (leading < input_bytes && !input[leading]) leading++;
  uint32_t needed = leading + digit_count;
  if (needed + 1 > capacity) return 0;
  uint32_t at = 0;
  for (uint32_t i = 0; i < leading; i++) out[at++] = '1';
  while (digit_count) out[at++] = base58_alphabet[digits[--digit_count]];
  out[at] = 0;
  return 1;
}

static int p256_did(const uint8_t public_key[64], char *out, uint32_t capacity) {
  uint8_t multikey[35];
  char encoded[64];
  multikey[0] = 0x80;
  multikey[1] = 0x24;
  multikey[2] = (public_key[63] & 1U) ? 0x03 : 0x02;
  for (uint32_t i = 0; i < 32; i++) multikey[3 + i] = public_key[i];
  if (!base58_encode(multikey, sizeof(multikey), encoded, sizeof(encoded))) return 0;
  struct bounded_buffer b = {(uint8_t *)out, 0, capacity, 1};
  put_text(&b, "did:key:z");
  put_text(&b, encoded);
  put_byte(&b, 0);
  return b.ok;
}

/* The 576-byte fixed-layout record `contracts/device-worker-canonical-v1.edn`
   describes.  C fills the slots; the object decides what text they denote,
   which is the whole point of moving the writer out of here -- a field order
   or a decimal is a claim about what this device asserts, and ADR-0015 draws
   the C boundary at mechanism. */
static void ctx_number(uint8_t *ctx, uint32_t offset, uint64_t value) {
  for (uint32_t i = 0; i < 8; i++)
    ctx[offset + i] = (uint8_t)(value >> (56U - i * 8U));
}

static void ctx_text(uint8_t *ctx, uint32_t offset, const char *text,
                     uint32_t bytes) {
  for (uint32_t i = 0; i < bytes; i++) ctx[offset + i] = (uint8_t)text[i];
}

/* Every numeric slot of a worker request, in one place, so the two callers
   below cannot drift.  A poll leaves job-id and the metrics zero; the object
   writes the `-` sentinel and does not read the slot. */
static void worker_context_numbers(
    uint8_t *ctx, uint32_t sequence, uint64_t job_id, uint32_t token,
    uint32_t second_token, uint32_t generated_tokens, uint32_t decode_tokens,
    uint64_t first_token_cycles, uint64_t decode_cycles,
    uint64_t inference_cycles, uint32_t vector_bits, uint32_t worker_threads,
    uint64_t tsc_hz, uint64_t output_token_count) {
  ctx_number(ctx, AIUEOS_DWC_SEQUENCE, sequence);
  ctx_number(ctx, AIUEOS_DWC_JOB_ID, job_id);
  ctx_number(ctx, AIUEOS_DWC_TOKEN, token);
  ctx_number(ctx, AIUEOS_DWC_SECOND_TOKEN, second_token);
  ctx_number(ctx, AIUEOS_DWC_GENERATED_TOKENS, generated_tokens);
  ctx_number(ctx, AIUEOS_DWC_DECODE_TOKENS, decode_tokens);
  ctx_number(ctx, AIUEOS_DWC_FIRST_TOKEN_CYCLES, first_token_cycles);
  ctx_number(ctx, AIUEOS_DWC_DECODE_CYCLES, decode_cycles);
  ctx_number(ctx, AIUEOS_DWC_INFERENCE_CYCLES, inference_cycles);
  ctx_number(ctx, AIUEOS_DWC_VECTOR_BITS, vector_bits);
  ctx_number(ctx, AIUEOS_DWC_WORKER_THREADS, worker_threads);
  ctx_number(ctx, AIUEOS_DWC_TSC_HZ, tsc_hz);
  ctx_number(ctx, AIUEOS_DWC_OUTPUT_TOKEN_COUNT, output_token_count);
}

static void canonical_field(struct bounded_buffer *b, const char *text) {
  put_byte(b, '\n');
  put_text(b, text);
}

static void canonical_number(struct bounded_buffer *b, uint64_t number) {
  put_byte(b, '\n');
  put_decimal(b, number);
}

static int decode_metrics_valid(uint32_t generated_tokens,
                                uint32_t decode_tokens,
                                uint64_t first_token_cycles,
                                uint64_t decode_cycles,
                                uint64_t inference_cycles,
                                uint32_t vector_bits,
                                uint32_t worker_threads) {
  return generated_tokens >= 2U && generated_tokens <= 8U &&
         decode_tokens == generated_tokens - 1U &&
         first_token_cycles && decode_cycles &&
         first_token_cycles <= UINT64_MAX - decode_cycles &&
         inference_cycles == first_token_cycles + decode_cycles &&
         (vector_bits == 0U || vector_bits == 256U) &&
         (worker_threads == 1U || worker_threads == 2U);
}

static int decode_metrics_empty(uint32_t generated_tokens,
                                uint32_t decode_tokens,
                                uint64_t first_token_cycles,
                                uint64_t decode_cycles,
                                uint64_t inference_cycles,
                                uint32_t vector_bits,
                                uint32_t worker_threads) {
  return !generated_tokens && !decode_tokens && !first_token_cycles &&
         !decode_cycles && !inference_cycles && !vector_bits &&
         !worker_threads;
}

uint32_t aiueos_device_result_http_request(
    const struct aiueos_device_result *result, uint8_t *out, uint32_t capacity,
    char *did_out, uint32_t did_capacity) {
  if (!result || !result->boot || !result->mac || !out || capacity < 512 ||
      !did_out || did_capacity < 48 ||
      result->boot->version < AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED ||
      !result->boot->tsc_hz ||
      !decode_metrics_valid(
        result->generated_tokens, result->decode_tokens,
        result->first_token_cycles, result->decode_cycles,
        result->inference_cycles, result->vector_bits,
        result->worker_threads)) return 0;

  uint8_t private_key[32] = {0}, public_key[64] = {0}, nonce_k[32] = {0};
  uint8_t nonce[16] = {0}, digest[32] = {0};
  uint8_t signature[64] = {0};
  uint32_t request_length = 0;
  /* A warm PXE reboot may reuse the same physical pages before the loader has
     cleared every kernel BSS page.  The qualification result is built once
     per native boot, so refresh here and let all worker requests from this
     boot reuse the resulting id. */
  if (!device_private_key(private_key) ||
      !kotoba_aiueos_ecdsa_p256_public(private_key, public_key, p256_workspace) ||
      !random_scalar(nonce_k) ||
      !device_boot_id_refresh() ||
      !aiueos_cpu_random_bytes(nonce, sizeof(nonce))) goto cleanup;
  if (!p256_did(public_key, did_out, did_capacity)) goto cleanup;

  char node[32] = "aiueos-k16-";
  for (uint32_t i = 0; i < 6; i++) {
    node[11 + i * 2] = hex_alphabet[result->mac[i] >> 4];
    node[12 + i * 2] = hex_alphabet[result->mac[i] & 15U];
  }
  node[23] = 0;
  char public_hex[129], boot_hex[17], model_hex[65], nonce_hex[33];
  hex_encode(public_key, 64, public_hex);
  hex_encode(device_boot_id, 8, boot_hex);
  hex_encode(result->boot->model_sha256, 32, model_hex);
  hex_encode(nonce, 16, nonce_hex);

  uint8_t canonical_bytes[DEVICE_CANONICAL_MAX];
  struct bounded_buffer canonical = {
    canonical_bytes, 0, sizeof(canonical_bytes), 1
  };
  put_text(&canonical, "aiueos-k16-result-v2");
  canonical_field(&canonical, node);
  canonical_field(&canonical, public_hex);
  canonical_field(&canonical, boot_hex);
  canonical_field(&canonical, model_hex);
  canonical_field(&canonical, "Qwen3.8-27B-UD-IQ3_XXS.gguf");
  canonical_number(&canonical, 2);
  canonical_number(&canonical, result->token);
  canonical_number(&canonical, result->second_token);
  canonical_number(&canonical, result->generated_tokens);
  canonical_number(&canonical, result->decode_tokens);
  canonical_number(&canonical, result->boot->model_load_cycles);
  canonical_number(&canonical, result->first_token_cycles);
  canonical_number(&canonical, result->decode_cycles);
  canonical_number(&canonical, result->inference_cycles);
  canonical_number(&canonical, result->vector_bits);
  canonical_number(&canonical, result->worker_threads);
  canonical_number(&canonical, result->boot->tsc_hz);
  canonical_field(&canonical, nonce_hex);
  if (!canonical.ok ||
      !kotoba_aiueos_sha256(canonical.bytes, canonical.length, digest,
                            sha_workspace, sizeof(sha_workspace)) ||
      !kotoba_aiueos_ecdsa_p256_sign(private_key, digest, nonce_k,
                                     signature, p256_workspace)) goto cleanup;
  char signature_hex[129];
  hex_encode(signature, 64, signature_hex);

  uint8_t body_bytes[DEVICE_BODY_MAX];
  struct bounded_buffer body = {body_bytes, 0, sizeof(body_bytes), 1};
  put_text(&body, "{\"node\":\""); put_text(&body, node);
  put_text(&body, "\",\"public-key\":\""); put_text(&body, public_hex);
  put_text(&body, "\",\"boot\":\""); put_text(&body, boot_hex);
  put_text(&body, "\",\"model-sha256\":\""); put_text(&body, model_hex);
  put_text(&body, "\",\"model\":\"Qwen3.8-27B-UD-IQ3_XXS.gguf\",\"protocol\":2,\"token\":");
  put_decimal(&body, result->token);
  put_text(&body, ",\"second-token\":"); put_decimal(&body, result->second_token);
  put_text(&body, ",\"generated-tokens\":");
  put_decimal(&body, result->generated_tokens);
  put_text(&body, ",\"decode-tokens\":");
  put_decimal(&body, result->decode_tokens);
  put_text(&body, ",\"model-load-cycles\":");
  put_decimal(&body, result->boot->model_load_cycles);
  put_text(&body, ",\"first-token-cycles\":");
  put_decimal(&body, result->first_token_cycles);
  put_text(&body, ",\"decode-cycles\":");
  put_decimal(&body, result->decode_cycles);
  put_text(&body, ",\"inference-cycles\":");
  put_decimal(&body, result->inference_cycles);
  put_text(&body, ",\"vector-bits\":"); put_decimal(&body, result->vector_bits);
  put_text(&body, ",\"worker-threads\":");
  put_decimal(&body, result->worker_threads);
  put_text(&body, ",\"tsc-hz\":"); put_decimal(&body, result->boot->tsc_hz);
  put_text(&body, ",\"nonce\":\""); put_text(&body, nonce_hex);
  put_text(&body, "\",\"signature\":\""); put_text(&body, signature_hex);
  put_text(&body, "\"}");
  if (!body.ok) goto cleanup;

  struct bounded_buffer request = {out, 0, capacity, 1};
  put_text(&request, "POST /infer/nodes/device-p256-result HTTP/1.1\r\n");
  put_text(&request, "Host: api.murakumo.cloud\r\n");
  put_text(&request, "User-Agent: aiueos-k16-node-v2\r\n");
  put_text(&request, "Content-Type: application/json\r\n");
  put_text(&request, "Accept: application/json\r\nContent-Length: ");
  put_decimal(&request, body.length);
  put_text(&request, "\r\nConnection: close\r\n\r\n");
  for (uint32_t i = 0; i < body.length; i++) put_byte(&request, body.bytes[i]);
  if (request.ok) request_length = request.length;

cleanup:
  secure_zero(private_key, sizeof(private_key));
  secure_zero(nonce_k, sizeof(nonce_k));
  secure_zero(digest, sizeof(digest));
  secure_zero(p256_workspace, sizeof(p256_workspace));
  return request_length;
}

uint32_t aiueos_device_worker_http_request(
    const struct aiueos_device_worker_request *worker,
    uint8_t *out, uint32_t capacity,
    char *did_out, uint32_t did_capacity) {
  if (!worker || !worker->boot || !worker->mac || !out || capacity < 512 ||
      !did_out || did_capacity < 48 || !worker->sequence ||
      worker->boot->version < AIUEOS_BOOT_INFO_VERSION_TSC_CALIBRATED ||
      !worker->boot->tsc_hz ||
      (worker->operation != AIUEOS_DEVICE_WORKER_POLL &&
       worker->operation != AIUEOS_DEVICE_WORKER_RESULT &&
       worker->operation != AIUEOS_DEVICE_WORKER_CONTROL_ACK) ||
      (worker->operation == AIUEOS_DEVICE_WORKER_POLL &&
       (worker->job_id || worker->token || worker->second_token ||
        !decode_metrics_empty(
          worker->generated_tokens, worker->decode_tokens,
          worker->first_token_cycles, worker->decode_cycles,
          worker->inference_cycles, worker->vector_bits,
          worker->worker_threads))) ||
      ((worker->operation == AIUEOS_DEVICE_WORKER_RESULT ||
        worker->operation == AIUEOS_DEVICE_WORKER_CONTROL_ACK) &&
       !worker->job_id) ||
      (worker->operation == AIUEOS_DEVICE_WORKER_CONTROL_ACK &&
       (worker->token || worker->second_token ||
        !decode_metrics_empty(
          worker->generated_tokens, worker->decode_tokens,
          worker->first_token_cycles, worker->decode_cycles,
          worker->inference_cycles, worker->vector_bits,
          worker->worker_threads))) ||
      (worker->operation == AIUEOS_DEVICE_WORKER_RESULT &&
       !decode_metrics_valid(
         worker->generated_tokens, worker->decode_tokens,
         worker->first_token_cycles, worker->decode_cycles,
         worker->inference_cycles, worker->vector_bits,
         worker->worker_threads)))
    return 0;

  uint8_t private_key[32] = {0}, public_key[64] = {0}, nonce_k[32] = {0};
  uint8_t nonce[16] = {0}, digest[32] = {0}, signature[64] = {0};
  uint32_t request_length = 0;
  if (!device_private_key(private_key) ||
      !kotoba_aiueos_ecdsa_p256_public(private_key, public_key, p256_workspace) ||
      !random_scalar(nonce_k) || !device_boot_id_ensure() ||
      !aiueos_cpu_random_bytes(nonce, sizeof(nonce))) goto cleanup;
  if (!p256_did(public_key, did_out, did_capacity)) goto cleanup;

  char node[32] = "aiueos-k16-";
  for (uint32_t i = 0; i < 6; i++) {
    node[11 + i * 2] = hex_alphabet[worker->mac[i] >> 4];
    node[12 + i * 2] = hex_alphabet[worker->mac[i] & 15U];
  }
  node[23] = 0;
  char public_hex[129], boot_hex[17], model_hex[65], nonce_hex[33];
  hex_encode(public_key, 64, public_hex);
  hex_encode(device_boot_id, 8, boot_hex);
  hex_encode(worker->boot->model_sha256, 32, model_hex);
  hex_encode(nonce, 16, nonce_hex);
  const char *operation = worker->operation == AIUEOS_DEVICE_WORKER_POLL ?
    "poll" : (worker->operation == AIUEOS_DEVICE_WORKER_RESULT ?
              "result" : "control-ack");

  /* The signed text is `device-worker-canonical.kotoba` since ADR-0136.  This
     function used to build it here with twenty put/canonical_ calls; what is
     left is filling a fixed-layout record.  `operation` below is still needed
     for the JSON body, which is a different string in a different order. */
  uint8_t canonical_bytes[DEVICE_CANONICAL_MAX];
  uint8_t worker_ctx[DEVICE_WORKER_CTX_BYTES];
  secure_zero(worker_ctx, sizeof(worker_ctx));
  worker_ctx[AIUEOS_DWC_PROTOCOL] = 2;                       /* protocol */
  worker_ctx[AIUEOS_DWC_OPERATION] = (uint8_t)worker->operation;
  worker_ctx[AIUEOS_DWC_STOP_REASON] = 0;                       /* stop-reason sentinel */
  worker_context_numbers(
    worker_ctx, worker->sequence, worker->job_id, worker->token,
    worker->second_token, worker->generated_tokens, worker->decode_tokens,
    worker->first_token_cycles, worker->decode_cycles,
    worker->inference_cycles, worker->vector_bits, worker->worker_threads,
    worker->boot->tsc_hz, 0);
  ctx_text(worker_ctx, AIUEOS_DWC_NODE, node, 23);
  ctx_text(worker_ctx, AIUEOS_DWC_PUBLIC_KEY, public_hex, 128);
  ctx_text(worker_ctx, AIUEOS_DWC_BOOT, boot_hex, 16);
  ctx_text(worker_ctx, AIUEOS_DWC_MODEL_SHA256, model_hex, 64);
  ctx_text(worker_ctx, AIUEOS_DWC_NONCE, nonce_hex, 32);
  int64_t canonical_length = kotoba_aiueos_device_worker_canonical(
    worker_ctx, sizeof(worker_ctx), canonical_bytes, sizeof(canonical_bytes));
  /* Zero is never returned, and a negative value is the clause that refused. */
  if (canonical_length <= 0 ||
      !kotoba_aiueos_sha256(canonical_bytes, (uint64_t)canonical_length, digest,
                            sha_workspace, sizeof(sha_workspace)) ||
      !kotoba_aiueos_ecdsa_p256_sign(private_key, digest, nonce_k,
                                     signature, p256_workspace)) goto cleanup;
  char signature_hex[129];
  hex_encode(signature, 64, signature_hex);

  uint8_t body_bytes[DEVICE_BODY_MAX];
  struct bounded_buffer body = {body_bytes, 0, sizeof(body_bytes), 1};
  put_text(&body, "{\"node\":\""); put_text(&body, node);
  put_text(&body, "\",\"public-key\":\""); put_text(&body, public_hex);
  put_text(&body, "\",\"boot\":\""); put_text(&body, boot_hex);
  put_text(&body, "\",\"model-sha256\":\""); put_text(&body, model_hex);
  put_text(&body, "\",\"sequence\":"); put_decimal(&body, worker->sequence);
  put_text(&body, ",\"operation\":\""); put_text(&body, operation);
  put_text(&body, "\",\"job-id\":\"");
  if (worker->operation == AIUEOS_DEVICE_WORKER_POLL)
    put_text(&body, "-");
  else
    put_decimal(&body, worker->job_id);
  put_text(&body, "\",\"protocol\":2,\"token\":");
  put_decimal(&body, worker->token);
  put_text(&body, ",\"second-token\":"); put_decimal(&body, worker->second_token);
  put_text(&body, ",\"generated-tokens\":");
  put_decimal(&body, worker->generated_tokens);
  put_text(&body, ",\"decode-tokens\":");
  put_decimal(&body, worker->decode_tokens);
  put_text(&body, ",\"first-token-cycles\":");
  put_decimal(&body, worker->first_token_cycles);
  put_text(&body, ",\"decode-cycles\":");
  put_decimal(&body, worker->decode_cycles);
  put_text(&body, ",\"inference-cycles\":");
  put_decimal(&body, worker->inference_cycles);
  put_text(&body, ",\"vector-bits\":");
  put_decimal(&body, worker->vector_bits);
  put_text(&body, ",\"worker-threads\":");
  put_decimal(&body, worker->worker_threads);
  put_text(&body, ",\"tsc-hz\":"); put_decimal(&body, worker->boot->tsc_hz);
  put_text(&body, ",\"nonce\":\""); put_text(&body, nonce_hex);
  put_text(&body, "\",\"signature\":\""); put_text(&body, signature_hex);
  put_text(&body, "\"}");
  if (!body.ok) goto cleanup;

  struct bounded_buffer request = {out, 0, capacity, 1};
  put_text(&request, "POST /infer/nodes/device-p256-worker HTTP/1.1\r\n");
  put_text(&request, "Host: api.murakumo.cloud\r\n");
  put_text(&request, "User-Agent: aiueos-k16-worker-v2\r\n");
  put_text(&request, "Content-Type: application/json\r\n");
  put_text(&request, "Accept: application/json\r\nContent-Length: ");
  put_decimal(&request, body.length);
  put_text(&request, "\r\nConnection: close\r\n\r\n");
  for (uint32_t i = 0; i < body.length; i++) put_byte(&request, body.bytes[i]);
  if (request.ok) request_length = request.length;

cleanup:
  secure_zero(private_key, sizeof(private_key));
  secure_zero(nonce_k, sizeof(nonce_k));
  secure_zero(digest, sizeof(digest));
  secure_zero(p256_workspace, sizeof(p256_workspace));
  return request_length;
}

