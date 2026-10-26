/* SPDX-License-Identifier: Apache-2.0 */
#include "device_worker_protocol.h"

/* MARSHALLING ONLY (ADR-0219). The parse of the murakumo poll response is
   `os/aiueos/kotoba/device-worker-poll-response.kotoba`, linked by
   build-uefi.sh; it writes a 32-byte record (layout in its header comment)
   and this file unpacks that record into the caller's struct. No search and
   no comparison lives here. */

extern int64_t kotoba_aiueos_device_worker_poll_response(
    const uint8_t *http, int64_t length, uint8_t *out);

static uint32_t get_u32(const uint8_t *at) {
  return (uint32_t)at[0] | ((uint32_t)at[1] << 8) | ((uint32_t)at[2] << 16) |
         ((uint32_t)at[3] << 24);
}

static uint64_t get_u64(const uint8_t *at) {
  return (uint64_t)get_u32(at) | ((uint64_t)get_u32(at + 4) << 32);
}

int aiueos_device_worker_poll_response(
    const uint8_t *http, uint32_t length,
    struct aiueos_device_worker_poll *poll) {
  uint8_t out[AIUEOS_DEVICE_WORKER_POLL_RECORD_BYTES];
  uint32_t i;
  if (!http || !poll) return 0;
  for (i = 0; i < sizeof(out); i++) out[i] = 0;
  if (kotoba_aiueos_device_worker_poll_response(http, (int64_t)length, out) != 1)
    return 0;
  *poll = (struct aiueos_device_worker_poll){0};
  poll->job_id = get_u64(out);
  poll->control_id = get_u64(out + 8);
  poll->bos_token = get_u32(out + 16);
  poll->ready = out[20];
  poll->has_job = out[21];
  poll->reboot_pxe = out[22];
  poll->restart_runtime = out[23];
  return 1;
}
