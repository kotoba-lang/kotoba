/* The text-building segment of kernel/device_result.c's aiueos_device_result_http_request before JUN-554 moved it to
   kotoba/device-result-text.o, verbatim, over prelude.h's stubs (SHA-256 captures the canonical text, signing returns
   the scripted signature). */
#define SEGMENT_NAME old_segment
#include "prelude.h"
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

#include "epilogue.h"
