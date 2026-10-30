/* Host test for os/aiueos/kernel/device_poll_scheduler.c (D1-D2): cadence,
   sequence allocation, and the murakumo.infer.backoff failure rules.  Built
   and run by os/aiueos/scripts/smoke-device-poll-scheduler.sh. */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../kernel/device_poll_scheduler.h"

#define CHECK(x) do { if (!(x)) { \
  fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #x); \
  return 1; } } while (0)

/* 3 GHz calibrated TSC: 1 ms = 3e6 ticks. */
#define TSC_HZ 3000000000ULL
#define MS(x) ((uint64_t)(x) * (TSC_HZ / 1000U))

static int test_cadence_and_sequence(void) {
  struct aiueos_poll_sched s;
  aiueos_poll_sched_init(&s, TSC_HZ, 1000);
  CHECK(aiueos_poll_sched_due(&s, 1000));
  CHECK(aiueos_poll_sched_take_sequence(&s) == 1);
  CHECK(aiueos_poll_sched_take_sequence(&s) == 2);
  CHECK(aiueos_poll_sched_take_sequence(&s) == 3);

  /* A fresh poll schedules the next one exactly one heartbeat period out. */
  aiueos_poll_sched_record(&s, 1000, AIUEOS_POLL_OUTCOME_OK,
                           AIUEOS_POLL_FAIL_REMOTE, 0);
  CHECK(!aiueos_poll_sched_due(&s, 1000 + MS(60000) - 1));
  CHECK(aiueos_poll_sched_due(&s, 1000 + MS(60000)));
  CHECK(s.last_delay_ms == AIUEOS_POLL_HEARTBEAT_MS);
  CHECK(s.consecutive_failures == 0);
  return 0;
}

static int test_failure_doubling(void) {
  struct aiueos_poll_sched s;
  static const uint64_t expected[6] = {
    10000, 20000, 40000, 80000, 120000, 120000
  };
  aiueos_poll_sched_init(&s, TSC_HZ, 0);
  for (uint32_t i = 0; i < 6; i++) {
    uint64_t due_after;
    aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_TRANSPORT,
                             AIUEOS_POLL_FAIL_REMOTE, 0);
    CHECK(s.last_delay_ms == expected[i]);
    due_after = s.next_due_tsc;
    CHECK(due_after == MS(expected[i]));
  }
  CHECK(s.consecutive_failures == 6);
  /* A success resets the curve. */
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_OK,
                           AIUEOS_POLL_FAIL_REMOTE, 0);
  CHECK(s.consecutive_failures == 0);
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_TRANSPORT,
                           AIUEOS_POLL_FAIL_REMOTE, 0);
  CHECK(s.last_delay_ms == expected[0]);
  return 0;
}

static int test_jitter(void) {
  struct aiueos_poll_sched s;
  aiueos_poll_sched_init(&s, TSC_HZ, 0);
  /* failures=1 -> raw 10000 ms; max spread is raw/4 = 2500. */
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_HTTP_ERROR,
                           AIUEOS_POLL_FAIL_REMOTE, 65535);
  CHECK(s.last_delay_ms > 10000);
  CHECK(s.last_delay_ms < 12500);
  aiueos_poll_sched_init(&s, TSC_HZ, 0);
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_HTTP_ERROR,
                           AIUEOS_POLL_FAIL_REMOTE, 32768);
  /* half of the 25% spread, integer rounding downward */
  CHECK(s.last_delay_ms >= 11250 && s.last_delay_ms <= 11251);
  return 0;
}

static int test_local_exhaustion(void) {
  struct aiueos_poll_sched s;
  /* Rule 2: local exhaustion jumps straight to the ceiling, regardless of
     how few failures there have been. */
  aiueos_poll_sched_init(&s, TSC_HZ, 0);
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_TRANSPORT,
                           AIUEOS_POLL_FAIL_LOCAL_EXHAUSTION, 0);
  CHECK(s.last_delay_ms == AIUEOS_POLL_BACKOFF_MAX_MS);
  CHECK(s.next_due_tsc == MS(AIUEOS_POLL_BACKOFF_MAX_MS));
  return 0;
}

static int test_enroll_and_conflict(void) {
  struct aiueos_poll_sched s;
  aiueos_poll_sched_init(&s, TSC_HZ, 0);
  /* 404: enrollment pending until the caller clears it. */
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_ENROLL,
                           AIUEOS_POLL_FAIL_REMOTE, 0);
  CHECK(s.enroll_pending == 1);
  CHECK(s.last_delay_ms == 10000);
  aiueos_poll_sched_clear_enroll(&s);
  CHECK(s.enroll_pending == 0);

  /* 409: the identity namespace must change (caller refreshes the boot id),
     so the sequence restarts and the conflict is counted. */
  CHECK(aiueos_poll_sched_take_sequence(&s) == 1);
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_SEQ_CONFLICT,
                           AIUEOS_POLL_FAIL_REMOTE, 0);
  CHECK(s.identity_refreshes == 1);
  CHECK(s.sequence == 0);
  CHECK(aiueos_poll_sched_take_sequence(&s) == 1);
  CHECK(s.last_delay_ms == 20000); /* second consecutive failure */

  /* Replay: understood but renewed nothing -- counted, cadence intact. */
  aiueos_poll_sched_record(&s, 0, AIUEOS_POLL_OUTCOME_REPLAY,
                           AIUEOS_POLL_FAIL_REMOTE, 0);
  CHECK(s.replays == 1);
  CHECK(s.consecutive_failures == 0);
  CHECK(s.last_delay_ms == AIUEOS_POLL_HEARTBEAT_MS);
  return 0;
}

static int test_status_disposition(void) {
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 200 OK\r\n", 17) == AIUEOS_POLL_OUTCOME_OK);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 201 Created\r\n", 21) == AIUEOS_POLL_OUTCOME_OK);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 404 Not Found\r\n", 23) == AIUEOS_POLL_OUTCOME_ENROLL);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 409 Conflict\r\n", 22) == AIUEOS_POLL_OUTCOME_SEQ_CONFLICT);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 500 Internal\r\n", 22) == AIUEOS_POLL_OUTCOME_HTTP_ERROR);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 429 Too Many\r\n", 22) == AIUEOS_POLL_OUTCOME_HTTP_ERROR);
  /* Not a status line at all, truncated, or a different minor version. */
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"GET / HTTP/1.1\r\n", 16) == AIUEOS_POLL_OUTCOME_TRANSPORT);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 2", 10) == AIUEOS_POLL_OUTCOME_TRANSPORT);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.0 200 OK\r\n", 17) == AIUEOS_POLL_OUTCOME_TRANSPORT);
  CHECK(aiueos_poll_sched_status_disposition(
           (const uint8_t *)"HTTP/1.1 2ab x\r\n", 16) == AIUEOS_POLL_OUTCOME_TRANSPORT);
  CHECK(aiueos_poll_sched_status_disposition(NULL, 0) == AIUEOS_POLL_OUTCOME_TRANSPORT);
  return 0;
}

int main(void) {
  CHECK(test_cadence_and_sequence() == 0);
  CHECK(test_failure_doubling() == 0);
  CHECK(test_jitter() == 0);
  CHECK(test_local_exhaustion() == 0);
  CHECK(test_enroll_and_conflict() == 0);
  CHECK(test_status_disposition() == 0);
  puts("AIUEOS_DEVICE_POLL_SCHEDULER_OK cadence=60s backoff=double-bounded-classified");
  return 0;
}
