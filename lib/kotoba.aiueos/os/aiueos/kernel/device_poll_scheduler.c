#include "device_poll_scheduler.h"

/* Implementation notes are in the header.  Mirrors the two pure functions of
   murakumo.infer.backoff (next-delay-ms / classify) in integer C:

     delay_ms(failures) = min(base * factor^failures, max) * (1 + jitter/4)
     local-exhaustion   -> max, immediately

   failures here is `consecutive_failures` AFTER the failed send (>= 1), so
   the first retry waits base*factor (10 s), matching `next-delay-ms` with
   failures=1.  Success schedules the heartbeat period (60 s) instead of the
   backoff base; that is the loop's normal cadence, R2/D1. */

static uint64_t ms_to_ticks(uint64_t tsc_hz, uint64_t ms) {
  /* tsc_hz * ms fits in 64 bits for any calibrated TSC (1e10 * 1.2e5 =
     1.2e15 < 1.8e19).  The /1000 is last, so sub-ms precision is kept. */
  return tsc_hz * ms / 1000U;
}

void aiueos_poll_sched_init(struct aiueos_poll_sched *s, uint64_t tsc_hz,
                            uint64_t now_tsc) {
  if (!s) return;
  s->tsc_hz = tsc_hz;
  s->next_due_tsc = now_tsc;
  s->sequence = 0;
  s->consecutive_failures = 0;
  s->identity_refreshes = 0;
  s->enroll_pending = 0;
  s->replays = 0;
  s->last_delay_ms = 0;
}

int aiueos_poll_sched_due(const struct aiueos_poll_sched *s, uint64_t now_tsc) {
  if (!s) return 0;
  return (int64_t)(now_tsc - s->next_due_tsc) >= 0;
}

uint32_t aiueos_poll_sched_take_sequence(struct aiueos_poll_sched *s) {
  if (!s) return 0;
  s->sequence++;
  return s->sequence;
}

void aiueos_poll_sched_clear_enroll(struct aiueos_poll_sched *s) {
  if (s) s->enroll_pending = 0;
}

/* next-delay-ms: base * factor^failures, capped, plus up to 25% jitter. */
static uint64_t failure_delay_ms(uint32_t failures, uint16_t jitter_u16) {
  uint64_t raw = AIUEOS_POLL_BACKOFF_BASE_MS;
  uint32_t f = failures;
  while (f && raw < AIUEOS_POLL_BACKOFF_MAX_MS) {
    raw *= AIUEOS_POLL_BACKOFF_FACTOR;
    f--;
  }
  if (raw > AIUEOS_POLL_BACKOFF_MAX_MS) raw = AIUEOS_POLL_BACKOFF_MAX_MS;
  /* spread = bounded * 0.25 * jitter, integer: (raw/4) * u16 / 65536. */
  return raw + (raw / 4U) * (uint64_t)jitter_u16 / 65536U;
}

static void schedule_in(struct aiueos_poll_sched *s, uint64_t now_tsc,
                        uint64_t delay_ms) {
  s->last_delay_ms = delay_ms;
  s->next_due_tsc = now_tsc + ms_to_ticks(s->tsc_hz, delay_ms);
}

void aiueos_poll_sched_record(struct aiueos_poll_sched *s, uint64_t now_tsc,
                              enum aiueos_poll_outcome outcome,
                              enum aiueos_poll_fail_class fail_class,
                              uint16_t jitter_u16) {
  if (!s) return;
  switch (outcome) {
  case AIUEOS_POLL_OUTCOME_OK:
    s->consecutive_failures = 0;
    schedule_in(s, now_tsc, AIUEOS_POLL_HEARTBEAT_MS);
    return;
  case AIUEOS_POLL_OUTCOME_REPLAY:
    /* The response was understood (2xx) but renewed nothing.  The cadence is
       healthy; the counter is the alarm. */
    s->replays++;
    s->consecutive_failures = 0;
    schedule_in(s, now_tsc, AIUEOS_POLL_HEARTBEAT_MS);
    return;
  case AIUEOS_POLL_OUTCOME_ENROLL:
    s->enroll_pending = 1;
    s->consecutive_failures++;
    schedule_in(s, now_tsc, failure_delay_ms(s->consecutive_failures, jitter_u16));
    return;
  case AIUEOS_POLL_OUTCOME_SEQ_CONFLICT:
    /* (did,boot,sequence) collided.  The caller refreshes the boot id; the
       sequence restarts because the identity namespace changes with it. */
    s->identity_refreshes++;
    s->sequence = 0;
    s->consecutive_failures++;
    schedule_in(s, now_tsc, failure_delay_ms(s->consecutive_failures, jitter_u16));
    return;
  case AIUEOS_POLL_OUTCOME_HTTP_ERROR:
    s->consecutive_failures++;
    schedule_in(s, now_tsc, failure_delay_ms(s->consecutive_failures, jitter_u16));
    return;
  case AIUEOS_POLL_OUTCOME_TRANSPORT:
  default:
    s->consecutive_failures++;
    /* Rule 2: local exhaustion jumps to the ceiling.  One connection per
       ceiling is not the ADR-260902 killer (that was one per 5 s, forever,
       unclassified). */
    if (fail_class == AIUEOS_POLL_FAIL_LOCAL_EXHAUSTION)
      schedule_in(s, now_tsc, AIUEOS_POLL_BACKOFF_MAX_MS);
    else
      schedule_in(s, now_tsc, failure_delay_ms(s->consecutive_failures, jitter_u16));
    return;
  }
}

enum aiueos_poll_outcome aiueos_poll_sched_status_disposition(
    const uint8_t *http, uint32_t length) {
  /* "HTTP/1.1 NNN ..." -- same shape the poll-response kotoba object admits
     ("HTTP/1.1 2").  Only the status number is mechanism here. */
  uint32_t status;
  if (!http || length < 12) return AIUEOS_POLL_OUTCOME_TRANSPORT;
  if (http[0] != 'H' || http[1] != 'T' || http[2] != 'T' || http[3] != 'P' ||
      http[4] != '/' || http[5] != '1' || http[6] != '.' || http[7] != '1' ||
      http[8] != ' ')
    return AIUEOS_POLL_OUTCOME_TRANSPORT;
  if (http[9] < '0' || http[9] > '9' || http[10] < '0' || http[10] > '9' ||
      http[11] < '0' || http[11] > '9')
    return AIUEOS_POLL_OUTCOME_TRANSPORT;
  status = (uint32_t)(http[9] - '0') * 100U + (uint32_t)(http[10] - '0') * 10U +
           (uint32_t)(http[11] - '0');
  if (status >= 200U && status < 300U) return AIUEOS_POLL_OUTCOME_OK;
  if (status == 404U) return AIUEOS_POLL_OUTCOME_ENROLL;
  if (status == 409U) return AIUEOS_POLL_OUTCOME_SEQ_CONFLICT;
  return AIUEOS_POLL_OUTCOME_HTTP_ERROR;
}
