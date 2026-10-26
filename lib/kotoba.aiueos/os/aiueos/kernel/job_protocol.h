/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_JOB_PROTOCOL_H
#define AIUEOS_JOB_PROTOCOL_H

#include <stdint.h>
#include "micro_infer.h"

#define AIUEOS_JOB_ID_MAX 20U
#define AIUEOS_JOB_REQUEST_CAPACITY 256U
#define AIUEOS_JOB_RESULT_CAPACITY 256U
#define AIUEOS_JOB_COMMIT_CAPACITY 128U
#define AIUEOS_NODE_LIVENESS_CAPACITY 128U

struct aiueos_job_request {
  uint64_t boot_nonce;
  uint8_t job_id[AIUEOS_JOB_ID_MAX+1U];
  uint8_t prompt[AIUEOS_MICRO_INFER_PROMPT_MAX];
  uint32_t prompt_length;
};

int aiueos_job_request_parse(
  const uint8_t *payload,uint32_t length,uint64_t expected_boot,
  struct aiueos_job_request *request);
uint32_t aiueos_job_result_payload(
  uint8_t *out,uint32_t capacity,uint64_t boot_nonce,const uint8_t *job_id,
  const struct aiueos_micro_infer_result *result,uint64_t inference_cycles);
int aiueos_job_commit_valid(
  const uint8_t *payload,uint32_t length,uint64_t boot_nonce,
  const uint8_t *job_id);
int aiueos_node_ping_parse(
  const uint8_t *payload,uint32_t length,uint64_t expected_boot,
  uint32_t *sequence);
uint32_t aiueos_node_pong_payload(
  uint8_t *out,uint32_t capacity,uint64_t boot_nonce,uint32_t sequence);

#endif
