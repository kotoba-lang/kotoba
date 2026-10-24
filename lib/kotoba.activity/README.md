# kotoba-activity

**Automatic work-time capture in pure Clojure.** A [kotoba-lang](https://github.com/kotoba-lang)
capability library for the product class the fleet had no answer to — automatic
timesheet capture, the Timely / Memtime / Rize / Clockk / DeskTime / RescueTime
category. Raw activity samples in, attributed timesheet entries out:

```
observations ──segment──▶ sessions ──attribute──▶ attributions ──▶ timesheet entries
                                   ╰──admit──▶ (the boundary an LLM proposal crosses)
```

No network, no I/O, no clock — anything needing the current time or a timezone
takes it from the caller, so a run is reproducible from its observations alone.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.

[`kotoba-lang/labor`](https://github.com/kotoba-lang/labor) is the sibling that
*prices* work time (contracts, wages, payroll). This library only ever says how
much time was **observed** and what it was for. `->timesheet-entries` emits the
`:ts/*` shape `kotoba.labor/timesheet` uses, so the two compose while neither
depends on the other.

## Maturity

| | |
|---|---|
| Role | capability |
| Dependencies | none |
| Tests | 32 tests, 87 assertions, all green |
| Runtime | `.cljc`, JVM + ClojureScript |
| Capture agents | not here — `cloud-itonami/kadou` ships three: desktop, git, calendar |

## The three invariants

These are what make the output usable as a billing basis instead of a guess,
and each has a test that fails if it stops holding.

1. **Time is never extrapolated.** A session ends at its last observation — not
   at the next one's start, not at "now". Capture undercounts by at most one
   sample interval per session. That is the safe direction; the alternative
   inflates every session by however long the poller happened to sleep.
2. **Unattributed time stays unattributed.** Nothing spreads leftover minutes
   across projects to make a day add up. A day where three hours of five were
   attributed is reported by `coverage` as a ratio of 0.6, not rounded up to a
   full one.
3. **Rounding only goes down or to nearest.** There is deliberately no `:ceil`;
   an unrecognised rounding mode falls back to `:floor`. Rounding up bills time
   nobody observed.

## Contract

```clojure
(require '[kotoba.activity :as a])

;; 1. observations — one sample of what was in front of the worker
(a/observation 1767225600000 :app "Emacs" :detail "activity.cljc")
;; => {:obs/at 1767225600000 :obs/source :app :obs/subject "Emacs"
;;     :obs/detail "activity.cljc" :obs/idle? false}

;; :detail is the privacy-sensitive part. Strip it before anything leaves
;; the worker's own device:
(a/redact observations)

;; 2. segment — samples to sessions. Idle samples are dropped, so an idle
;;    stretch becomes a gap, and a gap longer than :gap-ms closes the session.
(a/segment observations)                      ;; {:gap-ms 300000 :min-ms 60000}
(a/segment observations {:gap-ms 120000 :min-ms 0})
;; => [{:session/start .. :session/end .. :session/duration-ms ..
;;      :session/source :app :session/subject "Emacs" :session/detail ".."
;;      :session/samples 11}]

;; 3. attribute — sessions to projects, by declared rule. Every clause given
;;    must match (AND); a rule with no clauses matches nothing, so a
;;    catch-all cannot be written by omission.
(def rules
  [(a/rule :emacs-activity "kotoba-activity"
           :source :app :subject-is "Emacs" :detail-contains "activity" :weight 0.9)
   (a/rule :slack "internal" :source :app :subject-is "Slack" :weight 0.5)])

(a/attribute session rules)
;; => {:attribution/project "kotoba-activity" :attribution/confidence 0.9
;;     :attribution/evidence [:emacs-activity] :attribution/ambiguous? false}

(a/attribute-all sessions rules)   ;; => [{:session .. :attribution ..}]
```

The highest-weight match wins. When the top weight is shared by rules naming
*different* projects the session is left unattributed and flagged
`:attribution/ambiguous? true`, rather than resolved by rule order — a tie is a
real question about the worker's day, and answering it by list position hides
that.

```clojure
;; 4. admit — the boundary an externally produced (LLM) proposal crosses.
;;    The model may LABEL time. It may not create, lengthen or reassign it.
(a/admit {:session/start .. :session/end .. :duration-ms .. :project "p" :confidence 0.8}
         observed-sessions
         #{"p" "q"})
;; => {:admit/ok? true :admit/errors []}
```

| rejection | meaning |
|---|---|
| `:no-session` | cites a span that was not observed |
| `:unknown-project` | names a project outside the declared set |
| `:duration-mismatch` | restates a duration other than the observed one |
| `:bad-confidence` | confidence absent or outside 0.0–1.0 |
| `:low-confidence` | below `:confidence-floor` (default 0.6) |

```clojure
;; 5. coverage — what the day did and did not account for
(a/coverage attributed)
;; => {:coverage/observed-ms 3600000 :coverage/attributed-ms 1800000
;;     :coverage/unattributed-ms 1800000 :coverage/ratio 0.5}

;; 6. timesheet entries. date-of maps an epoch instant to a date string —
;;    supplied by the caller because the right answer depends on a timezone
;;    this library refuses to guess.
(a/->timesheet-entries "w-1" date-of attributed)                   ;; 15-min :floor
(a/->timesheet-entries "w-1" date-of attributed
                       {:increment-ms 360000 :rounding :nearest})  ;; 6-min :nearest
;; => [{:ts/worker "w-1" :ts/date "2026-01-01" :ts/project "kotoba-activity"
;;      :ts/hours 1.5 :ts/observed-ms 6000000}]

(a/total-hours entries)
```

`:ts/worker`, `:ts/date` and `:ts/hours` are exactly what
`kotoba.labor/wages-for` reads, so entries price unchanged:

```clojure
(require '[kotoba.labor :as labor])
(labor/wages-for (labor/contract "c-1" "w-1" "emp-1" "engineer" :hourly 12000)
                 (a/->timesheet-entries "w-1" date-of attributed))
```

## Where the samples come from

Not from here. This library is the pure core; collecting samples needs a
platform and a consent story, both of which live in the actor that wraps it:
[`cloud-itonami/kadou`](https://github.com/cloud-itonami/kadou) (稼働), whose
governor holds any proposal citing time that was not observed and refuses to
disclose another worker's window titles to a third party.

## Test

```bash
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0.
