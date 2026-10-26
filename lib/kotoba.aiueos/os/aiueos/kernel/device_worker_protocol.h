#ifndef AIUEOS_DEVICE_WORKER_PROTOCOL_H
#define AIUEOS_DEVICE_WORKER_PROTOCOL_H

#include <stdint.h>

/* The flat record the Kotoba parse writes (ADR-0219); layout in
   os/aiueos/kotoba/device-worker-poll-response.kotoba. */
#define AIUEOS_DEVICE_WORKER_POLL_RECORD_BYTES 32U

struct aiueos_device_worker_poll {
  uint64_t job_id;
  uint64_t control_id;
  uint32_t bos_token;
  int ready;
  int has_job;
  int reboot_pxe;
  int restart_runtime;
};

int aiueos_device_worker_poll_response(
    const uint8_t *http, uint32_t length,
    struct aiueos_device_worker_poll *poll);

#endif
