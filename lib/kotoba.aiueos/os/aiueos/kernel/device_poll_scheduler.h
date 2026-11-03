#ifndef AIUEOS_DEVICE_POLL_SCHEDULER_H
#define AIUEOS_DEVICE_POLL_SCHEDULER_H

/* When this node next signs and POSTs a device-P256 worker poll, and what it
   does with the answer.  SCHEDULING ONLY: building the signed request is
   `device_result.c`, sending it is the caller's transport, and what a response
   MEANS for jobs is the kotoba poll-response object (ADR-0219).  This module
   owns the three things that were previously open-coded at the call site:
   the 60 s heartbeat cadence (D1), the monotonic per-boot sequence (D2), and
   the failure wait.

   The failure wait follows the two rules of `murakumo.infer.backoff`
   (kotoba-lang/murakumo, ADR-260902-fleet-outbound-hygiene):
     1. a failure doubles the wait, bounded, with jitter so a fleet of nodes
        does not re-synchronise on the gateway;
     2. a failure is CLASSIFIED: "my own ports are exhausted" jumps straight
        to the ceiling and says so -- retrying faster makes it worse.
   Policy constants here differ from that namespace's default-policy in one
   way: the ceiling is 120 s, not 300 s, because R5 (heartbeat freshness)
   forbids backing off past the server's 120 s stale window
   (`node-heartbeat-stale-ms`).  The ADR-260902 trap was the FIXED 5 s retry
   with no classification and no bound; doubling + classify + bounded ceiling
   is what this module takes from that record.

   Pure C11, freestanding, no libc, no allocation, no globals: the kernel
   build (`zig cc -target x86_64-freestanding-none`) and the host smoke test
   (`os/aiueos/scripts/smoke-device-poll-scheduler.sh`) run the same bytes. */

#include <stdint.h>

/* The heartbeat period (D1): 60 s = 2x margin under the 120 s stale window.
   A successful poll schedules the next one this far out (TSC monotonic; the
   server's receive time is authoritative, so no wall clock is involved). */
#define AIUEOS_POLL_HEARTBEAT_MS 60000U

/* murakumo.infer.backoff default-policy shape: geometric doubling from a
   5 s base, ceiling as above. */
#define AIUEOS_POLL_BACKOFF_BASE_MS 5000U
#define AIUEOS_POLL_BACKOFF_MAX_MS 120000U
#define AIUEOS_POLL_BACKOFF_FACTOR 2U

enum aiueos_poll_outcome {
  /* 2xx and the response was understood.  Fresh poll = liveness renewed. */
  AIUEOS_POLL_OUTCOME_OK = 0,
  /* 2xx with "replay":true -- the server saw this exact (boot,sequence)
     before, so THIS send renewed nothing (device_p256.cljk:646-653).  Counted
     separately: a replay means the send design duplicated a sequence. */
  AIUEOS_POLL_OUTCOME_REPLAY,
  /* 404 "device must submit a qualification result before worker polling":
     not enrolled.  The caller must POST the qualification result next
     (that POST doubles as enrollment + first heartbeat). */
  AIUEOS_POLL_OUTCOME_ENROLL,
  /* 409: (did,boot,sequence) reused with different content.  The caller must
     refresh the boot id (new identity namespace) before the next send. */
  AIUEOS_POLL_OUTCOME_SEQ_CONFLICT,
  /* Any other non-2xx. */
  AIUEOS_POLL_OUTCOME_HTTP_ERROR,
  /* No usable response: transport failure, TLS failure, timeout. */
  AIUEOS_POLL_OUTCOME_TRANSPORT
};

enum aiueos_poll_fail_class {
  /* The far end did not answer (or answered unusably).  Geometric backoff. */
  AIUEOS_POLL_FAIL_REMOTE = 0,
  /* THIS host cannot open a socket (EADDRNOTAVAIL / EMFILE / ENFILE /
     ENOBUFS class).  Nothing this loop does frees ports faster: straight to
     the ceiling, loudly (rule 2). */
  AIUEOS_POLL_FAIL_LOCAL_EXHAUSTION = 1
};

struct aiueos_poll_sched {
  uint64_t tsc_hz;
  uint64_t next_due_tsc;        /* absolute TSC deadline of the next send */
  uint32_t sequence;            /* last issued; take_sequence returns ++ */
  uint32_t consecutive_failures;
  uint32_t identity_refreshes;  /* 409 count: boot-id refreshes requested */
  uint32_t enroll_pending;      /* 1 after 404, until the caller clears it */
  uint32_t replays;             /* "replay":true count */
  uint64_t last_delay_ms;       /* diagnostic: the wait just scheduled */
};

/* tsc_hz must be the calibrated boot-info value (>0).  The first poll is due
   immediately: enrollment happens through the qualification result POST, and
   until the server answers, liveness is not established anyway. */
void aiueos_poll_sched_init(struct aiueos_poll_sched *s, uint64_t tsc_hz,
                            uint64_t now_tsc);

/* 1 when now_tsc has reached the deadline.  Signed difference, so a TSC
   that somehow wrapped still compares correctly. */
int aiueos_poll_sched_due(const struct aiueos_poll_sched *s, uint64_t now_tsc);

/* Allocate the next sequence for a request about to be built.  Monotonic
   within a boot; every RETRY gets a fresh one too, because a retry with a
   reused (boot,sequence) but fresh nonce is a different request and would be
   a 409.  The fresh nonce is device_result.c's per-request job. */
uint32_t aiueos_poll_sched_take_sequence(struct aiueos_poll_sched *s);

/* Record what happened to the last send and schedule the next one.

   jitter_u16 spreads the fleet (rule 1): pass fresh entropy from
   aiueos_cpu_random_bytes, or 0 in tests.  The spread is bounded/4 of the
   computed wait (murakumo.infer.backoff: 25% of the bounded delay).
   fail_class is consulted only for TRANSPORT outcomes. */
void aiueos_poll_sched_record(struct aiueos_poll_sched *s, uint64_t now_tsc,
                              enum aiueos_poll_outcome outcome,
                              enum aiueos_poll_fail_class fail_class,
                              uint16_t jitter_u16);

/* The caller finished the qualification result POST (enrollment). */
void aiueos_poll_sched_clear_enroll(struct aiueos_poll_sched *s);

/* Map an HTTP response's status line to an outcome.  Mechanism only: reads
   "HTTP/1.1 NNN" and classifies the number.  A response without a parseable
   status line is TRANSPORT (nothing was understood).  Replay detection needs
   the body and is the poll-response object's business; a 2xx that parses is
   OK here. */
enum aiueos_poll_outcome aiueos_poll_sched_status_disposition(
    const uint8_t *http, uint32_t length);

/* ---------------------------------------------------------------------------
   Kernel-loop glue (JUN-35 gate B line-budget redesign).  These expand AT THE
   CALL SITE (kernel/main.c), not here: the serial diagnostics and the wait
   are main.c's file-local services, and gate B ("main.c 行数非増加に再設計して
   __LINE__ 固定") requires main.c to keep every evidence_stop(__LINE__) line
   number equal to the pre-PR file, so the block bodies live in this header
   and each call site in main.c spends exactly one line.  Requires in scope
   at the call site: aiueos_read_tsc, aiueos_k16_management_wait,
   debug_string, serial_string, serial_decimal (file-local in main.c),
   aiueos_cpu_random_bytes and aiueos_device_worker_identity_refresh
   (device_result.h).  `s` is evaluated more than once: pass an address,
   not an expression with side effects. */

/* D2 failure path: record the classified outcome (fresh jitter entropy;
   the disposition drives the wait -- murakumo.infer.backoff's two rules,
   double/bound/jitter and classify.  Not the fixed 5 s retry of
   ADR-260902), then the two diagnostics (404 = the qualification result
   POST is owed, D4; 409 = (did,boot,sequence) collision, move to a fresh
   identity namespace before the next send), then the wait. */
#define AIUEOS_POLL_SCHED_FAIL_WAIT(s, tsc_hz)                                 \
  do {                                                                         \
    extern enum aiueos_poll_outcome aiueos_rtl8125_device_worker_poll_outcome(void); \
    uint32_t refreshes_before = (s)->identity_refreshes;                       \
    uint16_t poll_jitter = 0;                                                  \
    (void)aiueos_cpu_random_bytes((uint8_t *)&poll_jitter,                     \
                                  sizeof(poll_jitter));                        \
    aiueos_poll_sched_record((s), aiueos_read_tsc(),                           \
      aiueos_rtl8125_device_worker_poll_outcome(),                             \
      AIUEOS_POLL_FAIL_REMOTE, poll_jitter);                                   \
    if ((s)->enroll_pending) {                                                 \
      /* 404: the qualification result POST must come first (it is             \
         enrollment + first heartbeat, D4).  Logged, not improvised:           \
         the persistent loop has no qualification metrics to send. */          \
      debug_string("AIUEOS_MURAKUMO_HEARTBEAT_UNENROLLED action=qualification-result-pending\n"); \
      serial_string("AIUEOS_MURAKUMO_HEARTBEAT_UNENROLLED action=qualification-result-pending wait-ms="); \
      serial_decimal((uint32_t)(s)->last_delay_ms);                            \
      serial_string("\r\n");                                                   \
    }                                                                          \
    if ((s)->identity_refreshes != refreshes_before) {                         \
      /* 409: (did,boot,sequence) collided; move to a fresh identity           \
         namespace (new boot id) before the next send. */                       \
      aiueos_device_worker_identity_refresh();                                 \
      debug_string("AIUEOS_MURAKUMO_SEQ_CONFLICT action=refresh-boot-id\n");   \
      serial_string("AIUEOS_MURAKUMO_SEQ_CONFLICT action=refresh-boot-id wait-ms="); \
      serial_decimal((uint32_t)(s)->last_delay_ms);                            \
      serial_string("\r\n");                                                   \
    }                                                                          \
    aiueos_k16_management_wait((tsc_hz),                                       \
      (uint32_t)(((s)->last_delay_ms + 999U) / 1000U));                        \
  } while (0)

/* Success path: fresh poll = liveness renewed -- the next one is one
   heartbeat period out (D1, 60 s; server stale window 120 s). */
#define AIUEOS_POLL_SCHED_SUCCESS_WAIT(s, tsc_hz)                              \
  do {                                                                         \
    aiueos_poll_sched_record((s), aiueos_read_tsc(), AIUEOS_POLL_OUTCOME_OK,   \
      AIUEOS_POLL_FAIL_REMOTE, 0);                                             \
    aiueos_k16_management_wait((tsc_hz),                                       \
      (uint32_t)(((s)->last_delay_ms + 999U) / 1000U));                        \
  } while (0)

#endif
