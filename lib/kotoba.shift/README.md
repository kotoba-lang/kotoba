# kotoba-shift

**Attendance in pure Clojure** — punches, shifts, rosters, coverage. A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the 打刻 /
rostering half of workforce management (the UKG / Dayforce / ADP / Deputy /
QuickBooks Time category).

```
punches ─pair-punches→ worked spans ─→ :ts/* entries
                    ╰→ anomalies
roster + demand ─coverage→ gaps        roster + worked ─variance→ absent / unrostered
```

## Sibling, not duplicate, of `kotoba.activity`

The two look alike and mean different things.
[`activity`](https://github.com/kotoba-lang/activity) **samples** — it asks "what
is in front of you just now", many times. This **records** — a punch is a
deliberate assertion that a shift began.

So `activity` segments a stream and undercounts by one sample interval; this
pairs discrete events and refuses to complete an unpaired one. And where
`activity` rounds to a billing increment, attendance is not rounded at all: 7h13m
stays 7h13m, because a punch is an assertion and rounding an assertion changes
what someone said.

The statutory side is deliberately **not** here — see
[`worklaw`](https://github.com/kotoba-lang/worklaw). Labour law applies to worked
time from any source, not just to time that came from a punch clock.

## Maturity

| | |
|---|---|
| Role | capability |
| Dependencies | none |
| Tests | 40 tests, 89 assertions, all green |
| Runtime | `.cljc`, JVM + ClojureScript |
| Actor | `cloud-itonami/kintai` (勤怠) |

## The invariant

**An unpaired punch is never completed.** A missing clock-out does not become
"end of shift", "end of day" or "now". It becomes an anomaly with no worked time
attached, because the alternative is inventing the most consequential number on
the timesheet.

```clojure
(sh/pair-punches [(sh/punch "w-1" nine :in)])
;; => {:worked []                                  ; not 8 hours. not anything.
;;     :anomalies [{:anomaly/rule :missing-out :anomaly/at nine}]}
```

The same refusal covers an unclosed break: how long the break was is
unreconstructable after the fact, so the span is reported rather than credited
whole.

## Contract

```clojure
(require '[kotoba.shift :as sh])

(sh/punch "w-1" at :in)          ;; :in :out :break-start :break-end
(sh/pair-punches punches)
;; => {:worked [{:worked/person "w-1" :worked/start .. :worked/end ..
;;               :worked/gross-ms .. :worked/break-ms .. :worked/ms ..}]
;;     :anomalies [...]}
```

| anomaly | |
|---|---|
| `:double-in` | a second `:in` while already clocked in |
| `:out-without-in` | an `:out` with no open `:in` |
| `:missing-out` | the period ends with an `:in` still open |
| `:break-outside` | a break punch while clocked out |
| `:double-break` | a `:break-start` while already on break |
| `:unclosed-break` | a `:break-start` with no `:break-end` before the `:out` |

Punches at the same instant are ordered `:out, :break-end, :break-start, :in`, so
a shift ending exactly as the next begins pairs correctly instead of reading as a
double clock-in. The consequence, which is real: an `:in` and an `:out` stamped
at the *same* instant read as `:out-without-in` then `:missing-out`, not as a
zero-length shift. Both readings say the terminal recorded something impossible;
this one says it without inventing an ordering the data does not contain.

```clojure
(sh/worked-ms worked)
(sh/worked-hours worked)
(sh/->timesheet-entries worked date-of)   ;; caller owns the timezone
(sh/describe-anomalies paired)            ;; "" on a clean day

;; Rostering
(sh/shift "s-1" "w-1" :nurse start end)
(sh/coverage roster (sh/demand :nurse from to 4))
;; => {:coverage/staffed 2 :coverage/gap 2 :coverage/surplus 0
;;     :coverage/partial ["s-3"]}

(sh/variance roster worked)
;; => [{:variance/kind :worked :variance/start-delta-ms -3600000 ...}
;;     {:variance/kind :absent ...}
;;     {:variance/kind :unrostered ...}]
```

`coverage` reports the gap and does not close it. A rostering tool that quietly
reassigns someone to fill a hole is how a person ends up working a shift they
never agreed to. A shift that only partly spans the demand window is listed
under `:coverage/partial` rather than counted as a fraction of a person, which
no shift can be staffed with.

## Availability, leave, swaps and generation

Everything below turns on **availability being declared, never inferred**. A
roster generator that does not know when someone is unavailable is one that will
schedule them anyway.

```clojure
(sh/availability "w-9" :nurse from to)
(sh/available? availabilities roster leave person role [from to])
;; false unless declared AND not already rostered AND not on APPROVED leave
```

**Leave accrual** is expressed per hours *worked*, not per calendar month — a
part-timer accrues in proportion, which is what most statutory schemes require
and what a monthly grant quietly gets wrong:

```clojure
(sh/accrual-policy :annual 1 20 :cap-hours 40)   ;; 1h per 20h worked, cap 40h
(sh/accrued policy worked taken-hours)
;; => {:balance/accrued 40 :balance/forfeited 10.0 :balance/available ..}
```

`:balance/forfeited` exists so a worker who lost ten hours to a cap can see the
ten hours.

**Shift swaps** need both sides:

```clojure
(-> (sh/swap-proposal "sw-1" "s-1" "w-1" "w-2")
    (sh/accept-swap "w-1") (sh/accept-swap "w-2"))
(sh/apply-swap roster availabilities leave proposal)
;; => {:roster [...] :applied? true}
;;    or {:applied? false :reason :not-accepted-by-both | :receiver-unavailable
;;                               | :not-their-shift | :no-such-shift}
```

A swap one person can impose on another is not a swap, it is a reassignment with
extra steps. The availability check on the receiver is the point: a swap is
exactly where someone quietly ends up working through their own approved leave.

**Roster generation proposes; it never closes a gap:**

```clojure
(sh/propose-roster roster availabilities leave demand candidates next-id)
;; => {:proposed [...] :still-short 1 :candidates-considered 3}
```

Nothing here mutates a roster. It names people who declared availability for
exactly this window and are free, and stops when it runs out of them — a gap
that cannot be filled from declared availability stays a gap rather than being
filled by whoever is least likely to object. Candidates are taken **in the order
given**, deliberately not "fairest" or "cheapest": ranking people for shift
assignment decides whose weekend gets taken, and it belongs to the operator who
can be held to it, not to a default buried in a library.

## Test

```bash
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0.
