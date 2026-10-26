/* SPDX-License-Identifier: Apache-2.0 */
#include "job_protocol.h"

/* MARSHALLING ONLY (ADR-0220). The four AIUEOS wire lines -- request,
   result, commit, liveness -- are decided by `os/aiueos/kotoba/aiueos/
   job_protocol.kotoba` behind the one kernel object
   `kotoba/job-protocol-dispatch.kotoba` (mode word + four arguments). This
   file packs the 48-byte input record that module's header lays out, hands
   spans across, and unpacks the answers into the caller's struct. No wire
   knowledge lives here: the id and prompt offsets are re-derived by the
   object, which is why a parsed request costs three calls. */

extern int64_t kotoba_aiueos_job_protocol(int64_t mode, int64_t a, int64_t b,
                                          int64_t c, int64_t d);

#define MODE_REQUEST_VERDICT 0
#define MODE_REQUEST_PROMPT 1
#define MODE_RESULT_WRITE 2
#define MODE_COMMIT_VALID 3
#define MODE_PING_VERDICT 4
#define MODE_PONG_WRITE 5
#define MODE_REQUEST_ID 6

#define IN_BYTES 48U

static void put_u32(uint8_t *at, uint32_t v) {
  at[0] = (uint8_t)v; at[1] = (uint8_t)(v >> 8);
  at[2] = (uint8_t)(v >> 16); at[3] = (uint8_t)(v >> 24);
}

static void put_u16(uint8_t *at, uint16_t v) {
  at[0] = (uint8_t)v; at[1] = (uint8_t)(v >> 8);
}

/* The record: boot nonce and cycle count as two u32 halves each, the
   micro-infer result, the sequence, and the id digits with their length. */
static uint32_t pack_in(uint8_t in[IN_BYTES], uint64_t boot_nonce,
                        uint64_t cycles,
                        const struct aiueos_micro_infer_result *result,
                        uint32_t sequence, const uint8_t *job_id) {
  uint32_t i, id_length = 0;
  for (i = 0; i < IN_BYTES; i++) in[i] = 0;
  put_u32(in + 0, (uint32_t)boot_nonce);
  put_u32(in + 4, (uint32_t)(boot_nonce >> 32));
  put_u32(in + 8, (uint32_t)cycles);
  put_u32(in + 12, (uint32_t)(cycles >> 32));
  if (result) {
    put_u16(in + 16, result->score);
    put_u16(in + 18, result->total);
    in[20] = result->token;
  }
  put_u32(in + 24, sequence);
  if (job_id) {
    /* text_length(job_id, AIUEOS_JOB_ID_MAX + 1): at most 21 bytes read */
    while (id_length <= AIUEOS_JOB_ID_MAX && job_id[id_length]) {
      if (id_length < AIUEOS_JOB_ID_MAX) in[28 + id_length] = job_id[id_length];
      id_length++;
    }
    in[21] = (uint8_t)(id_length > AIUEOS_JOB_ID_MAX ? 0 : id_length);
  }
  return id_length;
}

int aiueos_job_request_parse(
    const uint8_t *payload,uint32_t length,uint64_t expected_boot,
    struct aiueos_job_request *request) {
  int64_t verdict, id_length, prompt_length;
  uint32_t i;
  if (!payload || !request) return 0;
  verdict = kotoba_aiueos_job_protocol(
      MODE_REQUEST_VERDICT, (int64_t)(uintptr_t)payload, (int64_t)length,
      (int64_t)(uint32_t)(expected_boot >> 32), (int64_t)(uint32_t)expected_boot);
  if (verdict <= 0) return 0;
  for (i = 0; i < sizeof(request->job_id); i++) request->job_id[i] = 0;
  id_length = kotoba_aiueos_job_protocol(
      MODE_REQUEST_ID, (int64_t)(uintptr_t)payload, (int64_t)length,
      (int64_t)(uintptr_t)request->job_id, (int64_t)AIUEOS_JOB_ID_MAX);
  prompt_length = kotoba_aiueos_job_protocol(
      MODE_REQUEST_PROMPT, (int64_t)(uintptr_t)payload, (int64_t)length,
      (int64_t)(uintptr_t)request->prompt, (int64_t)AIUEOS_MICRO_INFER_PROMPT_MAX);
  if (id_length <= 0 || prompt_length <= 0) return 0;
  request->job_id[id_length] = 0;
  request->boot_nonce = expected_boot;
  request->prompt_length = (uint32_t)prompt_length;
  return 1;
}

uint32_t aiueos_job_result_payload(
    uint8_t *out,uint32_t capacity,uint64_t boot_nonce,const uint8_t *job_id,
    const struct aiueos_micro_infer_result *result,uint64_t inference_cycles) {
  uint8_t in[IN_BYTES];
  int64_t n;
  if (!out || !capacity || !result) return 0;
  pack_in(in, boot_nonce, inference_cycles, result, 0, job_id);
  n = kotoba_aiueos_job_protocol(MODE_RESULT_WRITE, (int64_t)(uintptr_t)out,
                                 (int64_t)capacity, (int64_t)(uintptr_t)in, 0);
  return n > 0 ? (uint32_t)n : 0;
}

int aiueos_job_commit_valid(
    const uint8_t *payload,uint32_t length,uint64_t boot_nonce,
    const uint8_t *job_id) {
  uint8_t in[IN_BYTES];
  if (!payload || !job_id) return 0;
  pack_in(in, boot_nonce, 0, 0, 0, job_id);
  return kotoba_aiueos_job_protocol(MODE_COMMIT_VALID,
                                    (int64_t)(uintptr_t)payload, (int64_t)length,
                                    (int64_t)(uintptr_t)in, 0) == 1;
}

int aiueos_node_ping_parse(
    const uint8_t *payload,uint32_t length,uint64_t expected_boot,
    uint32_t *sequence) {
  int64_t verdict;
  if (!payload || !sequence) return 0;
  verdict = kotoba_aiueos_job_protocol(
      MODE_PING_VERDICT, (int64_t)(uintptr_t)payload, (int64_t)length,
      (int64_t)(uint32_t)(expected_boot >> 32), (int64_t)(uint32_t)expected_boot);
  if (verdict < 0) return 0;
  *sequence = (uint32_t)verdict;
  return 1;
}

uint32_t aiueos_node_pong_payload(
    uint8_t *out,uint32_t capacity,uint64_t boot_nonce,uint32_t sequence) {
  uint8_t in[IN_BYTES];
  int64_t n;
  if (!out || !capacity) return 0;
  pack_in(in, boot_nonce, 0, 0, sequence, 0);
  n = kotoba_aiueos_job_protocol(MODE_PONG_WRITE, (int64_t)(uintptr_t)out,
                                 (int64_t)capacity, (int64_t)(uintptr_t)in, 0);
  return n > 0 ? (uint32_t)n : 0;
}
