/* SPDX-License-Identifier: Apache-2.0 */
#include "inference_status.h"

/* MARSHALLING ONLY (ADR-0219). The two decisions this file used to hold --
   whether a status record may be shown, and the milli-tokens-per-second
   arithmetic -- are `os/aiueos/kotoba/inference-status-valid.kotoba` and
   `os/aiueos/kotoba/inference-milli-tokens-per-second.kotoba`, linked by
   build-uefi.sh. What is left is packing the struct into the flat record
   the object reads, byte for byte, and no comparison: a pointer loaded from
   memory cannot be a region root on the guest side
   (:kotoba.error/kernel-region-provenance), so the struct crosses as one
   contiguous 200-byte record whose layout is the header comment of the
   object. Keep the two in step; the KIR contract
   (contracts/inference-status-valid-v1.edn) seeds records through
   `aiueos_inference_status_pack` below, so a layout drift turns it red. */

extern int64_t kotoba_aiueos_inference_status_valid(uint8_t *record,
                                                    int64_t length);
extern int64_t kotoba_aiueos_inference_milli_tokens_per_second(
    int64_t tokens, int64_t elapsed_ns);

static void put_u32(uint8_t *at, uint32_t v) {
  at[0] = (uint8_t)v; at[1] = (uint8_t)(v >> 8);
  at[2] = (uint8_t)(v >> 16); at[3] = (uint8_t)(v >> 24);
}

static void put_u64(uint8_t *at, uint64_t v) {
  put_u32(at, (uint32_t)v); put_u32(at + 4, (uint32_t)(v >> 32));
}

/* text[0..32] copied up to and including the first NUL -- the same 33 bytes
   the retired scan read -- and the presence flag at `flag`. */
static void put_text(uint8_t *record, uint32_t flag, uint32_t at,
                     const char *text) {
  uint32_t i;
  record[flag] = text ? 1 : 0;
  if (!text) return;
  for (i = 0; i <= AIUEOS_INFERENCE_STATUS_TEXT_MAX; i++) {
    record[at + i] = (uint8_t)text[i];
    if (!text[i]) return;
  }
}

void aiueos_inference_status_pack(const struct aiueos_inference_status *s,
                                  uint8_t record[AIUEOS_INFERENCE_STATUS_RECORD_BYTES]) {
  uint32_t i;
  for (i = 0; i < AIUEOS_INFERENCE_STATUS_RECORD_BYTES; i++) record[i] = 0;
  put_u32(record + 8, (uint32_t)sizeof(*s));
  record[88] = s ? 1 : 0;
  if (!s) return;
  put_u32(record + 0, s->abi_version);
  put_u32(record + 4, s->byte_size);
  put_u32(record + 12, (uint32_t)s->phase);
  put_u32(record + 16, s->prompt_tokens);
  put_u32(record + 20, s->generated_tokens);
  put_u32(record + 24, s->decode_tokens);
  put_u32(record + 28, s->target_tokens);
  put_u64(record + 32, s->artifact_bytes);
  put_u64(record + 40, s->resident_bytes);
  put_u64(record + 48, s->load_ns);
  put_u64(record + 56, s->prefill_ns);
  put_u64(record + 64, s->decode_ns);
  put_u64(record + 72, s->time_to_first_token_ns);
  put_u64(record + 80, s->compute_cycles);
  put_text(record, 89, 96, s->model);
  put_text(record, 90, 129, s->quant);
  put_text(record, 91, 162, s->detail);
}

int aiueos_inference_status_valid(const struct aiueos_inference_status *status) {
  /* .bss rather than a frame: the kernel's stacks are 4 KiB. The screen and
     the serial report call this from one thread at a time. */
  static uint8_t record[AIUEOS_INFERENCE_STATUS_RECORD_BYTES];
  aiueos_inference_status_pack(status, record);
  return kotoba_aiueos_inference_status_valid(
             record, AIUEOS_INFERENCE_STATUS_RECORD_BYTES) == 1;
}

uint64_t aiueos_inference_milli_tokens_per_second(uint32_t tokens,
                                                  uint64_t elapsed_ns) {
  return (uint64_t)kotoba_aiueos_inference_milli_tokens_per_second(
      (int64_t)tokens, (int64_t)elapsed_ns);
}
