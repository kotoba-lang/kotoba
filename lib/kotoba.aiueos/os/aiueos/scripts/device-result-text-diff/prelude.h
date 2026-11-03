/* What the text-building segment of aiueos_device_result_http_request reads and calls, for
   scripts/device-result-text-diff. The segment is pasted between this and epilogue.h into one function. */
#include <stdint.h>
#include "device_result.h"
#define DEVICE_CANONICAL_MAX 1024U
#define DEVICE_BODY_MAX 1024U
#define DEVICE_RESULT_TEXT_RECORD 288U
extern int64_t kotoba_aiueos_device_result_text(const uint8_t *, uint64_t, uint64_t, uint8_t *, uint64_t);
extern uint8_t device_boot_id[8];
extern uint8_t captured[2048]; extern uint32_t captured_length; extern uint8_t scripted_signature[64];
static uint8_t sha_workspace[8], p256_workspace[8];
static const char hex_alphabet[] = "0123456789abcdef";
struct bounded_buffer { uint8_t *bytes; uint32_t length, capacity; int ok; };
static void secure_zero(void *memory, uint32_t bytes) { volatile uint8_t *o = (volatile uint8_t *)memory; while (bytes--) *o++ = 0; }
static void put_byte(struct bounded_buffer *b, uint8_t value) { if (!b->ok || b->length >= b->capacity) { b->ok = 0; return; } b->bytes[b->length++] = value; }
static void put_text(struct bounded_buffer *b, const char *text) { if (!text) { b->ok = 0; return; } while (*text) put_byte(b, (uint8_t)*text++); }
static void put_decimal(struct bounded_buffer *b, uint64_t value) {
  char digits[20]; uint32_t n = 0;
  do { digits[n++] = (char)('0' + value % 10U); value /= 10U; } while (value && n < sizeof(digits));
  while (n) put_byte(b, (uint8_t)digits[--n]); }
static void hex_encode(const uint8_t *in, uint32_t bytes, char *out) {
  for (uint32_t i = 0; i < bytes; i++) { out[i * 2] = hex_alphabet[in[i] >> 4]; out[i * 2 + 1] = hex_alphabet[in[i] & 15U]; }
  out[bytes * 2] = 0; }
static void canonical_field(struct bounded_buffer *b, const char *text) { put_byte(b, '\n'); put_text(b, text); }
static void canonical_number(struct bounded_buffer *b, uint64_t number) { put_byte(b, '\n'); put_decimal(b, number); }
static void ctx_number(uint8_t *ctx, uint32_t offset, uint64_t value) { for (uint32_t i = 0; i < 8; i++) ctx[offset + i] = (uint8_t)(value >> (56U - i * 8U)); }
static uint64_t kotoba_aiueos_sha256(const uint8_t *in, uint64_t n, uint8_t *digest, uint8_t *ws, uint64_t wn) {
  (void)ws; (void)wn; for (uint64_t i = 0; i < n && i < 2048; i++) captured[i] = in[i]; captured_length = (uint32_t)n;
  for (int i = 0; i < 32; i++) digest[i] = (uint8_t)i; return 1; }
static uint64_t kotoba_aiueos_ecdsa_p256_sign(const uint8_t *k, const uint8_t *d, const uint8_t *nk, uint8_t *sig, uint8_t *ws) {
  (void)k; (void)d; (void)nk; (void)ws; for (int i = 0; i < 64; i++) sig[i] = scripted_signature[i]; return 1; }
/* returns the body length (0: the segment refused), the canonical text in captured[0..captured_length) */
uint32_t SEGMENT_NAME(const struct aiueos_device_result *result, const uint8_t public_key[64], const uint8_t nonce[16],
                      uint8_t *body_out) {
  uint8_t private_key[32] = {0}, nonce_k[32] = {0}, digest[32] = {0}, signature[64] = {0};
  uint32_t body_length = 0;
  (void)private_key; (void)nonce_k;
