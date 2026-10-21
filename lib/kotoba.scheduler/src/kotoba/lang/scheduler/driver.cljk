(ns kotoba.lang.scheduler.driver
  "A durable-outer-loop REFERENCE DRIVER for kotoba.lang.scheduler --
  concrete lease/tick/budget/checkpoint wiring through scheduler+async+time,
  the end-to-end example this library's own README describes only in
  prose ('the host drives the loop') without ever showing. Previously
  flagged: kotoba-lang/kotoba-lang's docs/lang/coverage.edn tracks this
  under :engineering-gaps/:async-runtime as '{:status :by-design :note
  \"... gap is durable-outer-loop reference drivers threading async+
  time+scheduler, not a tokio\"}' -- this namespace is that driver.

  Same discipline every namespace in this stdlib already follows: pure
  data, pure transitions, no threads, no wall-clock, no I/O of its own.
  A host (a real daemon, a kotoba-WASM guest, a test) calls `run-tick!`
  in a loop, persisting/reading the `checkpoint` between calls however it
  likes (disk, a KV store, nothing at all for a single-process run) --
  this namespace never touches storage itself, matching
  kotoba.lang.time's own 'host-injected clock, never reads the OS clock'
  discipline. The lease/epoch shape mirrors kototama.fleet's 'higher
  epoch wins on a shared store' fencing model elsewhere in this org,
  kept host-agnostic here since this library has no storage layer of its
  own to enforce it -- only the data shape a host's own claim/reclaim
  logic wires into.

  Zero third-party runtime deps; .cljc (JVM / SCI / CLJS / GraalVM / kotoba-WASM)."
  (:require [kotoba.lang.scheduler :as sch]
            [kotoba.lang.async :as a]))

(defn lease
  "A fencing token: `holder` names the process/run claiming this loop;
  `epoch` is a monotonically-advancing integer a host bumps on every
  reclaim. Pure data -- this library enforces nothing about HOW a host
  claims one, only what a valid token looks like."
  [holder epoch]
  {:holder holder :epoch epoch})

(defn lease-valid?
  "True iff CANDIDATE's epoch is not behind CURRENT's. A host runs this
  before trusting a checkpoint it's about to resume -- a checkpoint
  written under a since-superseded, lower epoch is stale and must not
  be resumed (the same 'higher epoch wins' invariant kototama.fleet
  already establishes for its own shared-store fencing, restated here
  in a storage-agnostic form)."
  [current candidate]
  (>= (:epoch candidate) (:epoch current)))

(defn checkpoint
  "A snapshot of a running durable loop: scheduler state, remaining tick
  budget, and the lease token. `:budget` and `:lease` are plain EDN and
  round-trip through any store as-is; `:scheduler` does NOT fully
  round-trip through `pr-str`/`read-string` on its own -- it carries the
  host-injected `:clock` fn and each job's `:fn` callback (the same
  scope kotoba.lang.scheduler itself never claims EDN-serializability
  for either). A host persisting a real checkpoint stores job/clock
  IDENTITY (a symbol, a registry key) and re-resolves the callback on
  resume, the same 'reference the handler, don't serialize the
  closure' pattern any durable-job system needs regardless of this
  library -- out of scope for this reference driver to reinvent."
  [scheduler-state budget lease]
  {:scheduler scheduler-state :budget budget :lease lease})

(defn exhausted?
  "True iff CKPT's tick budget is spent. This namespace never stops a
  loop itself (it has no runtime to stop) -- a host checks this as its
  own loop's exit condition, same as it checks `sch/due?` to decide
  whether to keep advancing `now` at all."
  [ckpt]
  (<= (:budget ckpt) 0))

(defn run-tick!
  "One durable-outer-loop step: fires all jobs due at `now` (via
  kotoba.lang.scheduler/tick) unless the budget is already exhausted.
  Budget is spent by the COUNT OF JOBS ACTUALLY FIRED, not by the tick
  call itself -- an idle tick with nothing due is a no-op that must not
  starve a loop that's simply waiting for its next scheduled job.
  Returns `[checkpoint' fired]`; the host persists checkpoint' (however
  it likes) before the next call -- this fn assumes the lease was
  already validated (`lease-valid?`) by the caller, it doesn't re-check
  authority itself, matching every other pure-transition fn in this
  stdlib not owning its own authority decisions (kotoba.lang.async/put
  doesn't check who's allowed to enqueue either)."
  [ckpt now]
  (if (exhausted? ckpt)
    [ckpt []]
    (let [[sch' fired] (sch/tick (:scheduler ckpt) now)
          spent (count fired)]
      [(assoc ckpt :scheduler sch' :budget (- (:budget ckpt) spent)) fired])))

(defn drain-ready!
  "Drain the scheduler's ready-queue inside a checkpoint
  (kotoba.lang.async/drain), returning `[checkpoint' records]` -- the
  host's observation step, the exact contract kotoba.lang.scheduler/tick's
  own docstring already describes (drain the ready-queue to see which
  jobs actually fired, across one or many prior ticks)."
  [ckpt]
  (let [[q' vals] (a/drain (:ready-queue (:scheduler ckpt)))]
    [(assoc-in ckpt [:scheduler :ready-queue] q') vals]))
