/* kernel/device_result.c's p256_did and base58_encode before JUN-554 moved them to kotoba/p256-did.o, verbatim, with the
   bounded_buffer, put_byte and put_text they use (p256_did renamed old_p256_did and made external). */
#include <stdint.h>
static const char base58_alphabet[] =
  "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
struct bounded_buffer {
  uint8_t *bytes;
  uint32_t length, capacity;
  int ok;
};

static void put_byte(struct bounded_buffer *b, uint8_t value) {
  if (!b->ok || b->length >= b->capacity) { b->ok = 0; return; }
  b->bytes[b->length++] = value;
}

static void put_text(struct bounded_buffer *b, const char *text) {
  if (!text) { b->ok = 0; return; }
  while (*text) put_byte(b, (uint8_t)*text++);
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

int old_p256_did(const uint8_t public_key[64], char *out, uint32_t capacity) {
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

