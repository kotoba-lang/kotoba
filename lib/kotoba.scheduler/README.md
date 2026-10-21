# kotoba-lang/scheduler

[![CI](https://github.com/kotoba-lang/scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/scheduler/actions/workflows/ci.yml)

A **durable tick scheduler** layered on the kotoba-lang foundational stdlib —
the bounded, time-driven loop a kotoba actor's durable outer loop (lease /
tick / budget) is built on. Consumes the sibling libs
[`async`](https://github.com/kotoba-lang/async) (bounded ready-queue),
[`time`](https://github.com/kotoba-lang/time) (clock + intervals), and
[`coll`](https://github.com/kotoba-lang/coll) (job shaping) — a real consumer
of all three (M5 for each). No third-party deps; every namespace is `.cljc`
(JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why

The kotoba-WASM premise forbids threads and wall-clock, so a scheduler can't
spawn goroutines or read `System/currentTimeMillis`. Instead it models a tick
loop as a pure state machine: the host advances `now` (an injected `clock`
from `kotoba.lang.time`), `tick` fires the due jobs from an `async` bounded
ready-queue, and `coll` shapes the job table. The host drives the loop; the
scheduler is pure transition — same shape as `langgraph` interrupts and the
durable outer loop in `AGENTS.md`.

## Current surface

`kotoba.lang.scheduler`:

- `scheduler` — make a scheduler from a `clock` (time) and a `ready-queue`
  (async channel; defaults to a bounded `:dropping` channel)
- `at` / `every` — schedule a job at an instant / at a fixed interval
- `tick` — fire all jobs due at `now`; returns `[scheduler fired-jobs]`
- `due?` — predicate: any jobs due at `now`?
- `cancel` — remove a job by id

A job is `{:id :at :fn :interval?}`. `tick` drains the due jobs (firing each
`fn` with `now`), re-enqueues interval jobs at `at + interval`.

`kotoba.lang.scheduler.driver` — a durable-outer-loop REFERENCE DRIVER
threading `scheduler`+`async`+`time` end-to-end (lease/tick/budget/
checkpoint), the concrete example this README described only in prose
above until now:

- `lease` / `lease-valid?` — a fencing token (`{:holder :epoch}`) and the
  "higher epoch wins" check a host runs before trusting a checkpoint
- `checkpoint` — `{:scheduler :budget :lease}`; `:budget`/`:lease` are
  plain EDN, `:scheduler` carries the host-injected clock/job-callback
  fns (see its docstring for why that's not a gap this driver invents)
- `run-tick!` — one durable-outer-loop step: fires due jobs via
  `scheduler/tick` and spends the budget by the COUNT OF JOBS ACTUALLY
  FIRED (an idle tick with nothing due never starves a waiting loop);
  stops firing once the budget is exhausted
- `exhausted?` — a checkpoint's own stop condition, for the host's loop
- `drain-ready!` — drains the checkpoint's ready-queue, observing what
  fired across one or many prior ticks

## Install

```clojure
io.github.kotoba-lang/scheduler {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.scheduler :as sch]
         '[kotoba.lang.time :as t])

(let [clock (fn [] 0)                                    ; injected, advances with time
      s (sch/scheduler clock)]
  (-> s
      (sch/at :a (t/instant 1000) (fn [now] (println "once" now)))
      (sch/every :b (t/seconds 500) (fn [now] (println "tick" now)) :start (t/instant 500))
      (sch/tick 499)   ;=> nothing due
      (sch/tick 500))  ;=> fires :b once, re-enqueues at 1000
```

A durable outer loop, using `kotoba.lang.scheduler.driver`:

```clojure
(require '[kotoba.lang.scheduler :as sch]
         '[kotoba.lang.scheduler.driver :as d]
         '[kotoba.lang.time :as t])

(let [clock (fn [] 0)
      s (sch/every (sch/scheduler clock) :heartbeat (t/seconds 1)
                   (fn [now] (println "beat" now)) :start (t/instant 1000))
      ;; a host claims a lease (however it likes) before driving the loop
      ckpt (d/checkpoint s 10 (d/lease "worker-1" 1))]
  (loop [ckpt ckpt now 1000]
    (when-not (d/exhausted? ckpt)
      (let [[ckpt' _fired] (d/run-tick! ckpt (t/instant now))]
        ;; persist ckpt' however the host likes here, then continue
        (recur ckpt' (+ now 1000))))))
```

## Verify

```sh
kbb -M:test
```
