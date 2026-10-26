#ifndef AIUEOS_DEVICE_RESULT_H
#define AIUEOS_DEVICE_RESULT_H

#include <stdint.h>
#include "../include/boot_info.h"

struct aiueos_device_result {
  const struct aiueos_boot_info *boot;
  const uint8_t *mac;
  uint32_t token;
  uint32_t second_token;
  uint32_t generated_tokens;
  uint32_t decode_tokens;
  uint64_t first_token_cycles;
  uint64_t decode_cycles;
  uint64_t inference_cycles;
  uint32_t vector_bits;
  uint32_t worker_threads;
};

enum aiueos_device_worker_operation {
  AIUEOS_DEVICE_WORKER_POLL = 1,
  AIUEOS_DEVICE_WORKER_RESULT = 2,
  AIUEOS_DEVICE_WORKER_CONTROL_ACK = 3
};

struct aiueos_device_worker_request {
  const struct aiueos_boot_info *boot;
  const uint8_t *mac;
  uint32_t sequence;
  enum aiueos_device_worker_operation operation;
  uint64_t job_id;
  uint32_t token;
  uint32_t second_token;
  uint32_t generated_tokens;
  uint32_t decode_tokens;
  uint64_t first_token_cycles;
  uint64_t decode_cycles;
  uint64_t inference_cycles;
  uint32_t vector_bits;
  uint32_t worker_threads;
};

/* The fixed-layout record `kotoba_aiueos_device_worker_canonical` reads.
   Declared here rather than inside `device_result.c` because TWO translation
   units fill one: that function, and the boot self-test in `main.c` that runs
   the object against the bytes the C writer produced.  The offsets are the
   contract's -- `os/aiueos/contracts/device-worker-canonical-v1.edn` :ctx --
   and a second literal copy of them is exactly the drift this avoids.

   Numbers are 8-byte BIG-ENDIAN with a zero most significant byte, so the
   admitted range is 0..2^56-1.  Text fields are fixed-width ASCII with no
   terminator.  Protocol 3 fills 368/432/104/2; protocol 2 must leave them at
   zero, and the object refuses (-7, -5) if it does not. */
#define AIUEOS_DEVICE_WORKER_CTX_BYTES 576U
#define AIUEOS_DEVICE_WORKER_CANONICAL_MAX 1024U
#define AIUEOS_DWC_PROTOCOL 0U
#define AIUEOS_DWC_OPERATION 1U
#define AIUEOS_DWC_STOP_REASON 2U
#define AIUEOS_DWC_SEQUENCE 8U
#define AIUEOS_DWC_JOB_ID 16U
#define AIUEOS_DWC_TOKEN 24U
#define AIUEOS_DWC_SECOND_TOKEN 32U
#define AIUEOS_DWC_GENERATED_TOKENS 40U
#define AIUEOS_DWC_DECODE_TOKENS 48U
#define AIUEOS_DWC_FIRST_TOKEN_CYCLES 56U
#define AIUEOS_DWC_DECODE_CYCLES 64U
#define AIUEOS_DWC_INFERENCE_CYCLES 72U
#define AIUEOS_DWC_VECTOR_BITS 80U
#define AIUEOS_DWC_WORKER_THREADS 88U
#define AIUEOS_DWC_TSC_HZ 96U
#define AIUEOS_DWC_OUTPUT_TOKEN_COUNT 104U
#define AIUEOS_DWC_NODE 128U
#define AIUEOS_DWC_PUBLIC_KEY 160U
#define AIUEOS_DWC_BOOT 288U
#define AIUEOS_DWC_MODEL_SHA256 304U
#define AIUEOS_DWC_INPUT_SHA256 368U
#define AIUEOS_DWC_OUTPUT_SHA256 432U
#define AIUEOS_DWC_NONCE 496U

/* NOT A BOOLEAN and zero is not success: positive is the number of bytes
   written, -1..-7 name the clause that refused. */
extern int64_t kotoba_aiueos_device_worker_canonical(
    uint8_t *ctx, uint64_t ctx_len, uint8_t *out, uint64_t out_cap);

int aiueos_cpu_random_bytes(uint8_t *out, uint32_t bytes);
uint32_t aiueos_device_result_http_request(
    const struct aiueos_device_result *result, uint8_t *out, uint32_t capacity,
    char *did_out, uint32_t did_capacity);
uint32_t aiueos_device_worker_http_request(
    const struct aiueos_device_worker_request *request,
    uint8_t *out, uint32_t capacity,
    char *did_out, uint32_t did_capacity);

#endif
