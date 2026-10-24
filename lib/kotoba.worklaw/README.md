# kotoba-worklaw

**Statutory working-time limits, by jurisdiction** — a
[kotoba-lang](https://github.com/kotoba-lang) capability library that answers one
question: does this worked time break a statutory limit here?

> **Not legal advice.** This is a mechanism plus a small, cited rule set. It is
> deliberately incomplete, and its most important behaviour is what it does about
> that.

## The invariant: silence is never compliance

Everything else in here is ordinary arithmetic. This is the reason the library
exists.

**An unchecked jurisdiction never returns "no violations."**

```clojure
(law/check twenty-three-hour-day [:atlantis] date-of {:period week})
;; => {:worklaw/coverage :none
;;     :worklaw/unchecked [[:atlantis]]
;;     :worklaw/violations []}          ; empty, and it means NOTHING WAS CHECKED

(law/compliant? that)   ;; => false
```

`compliant?` is deliberately not `(empty? violations)`. A caller who reaches for
the convenient boolean gets the conservative answer rather than the flattering
one.

## Jurisdictions are paths, not codes

`[:jp]`, `[:us]`, `[:us :ca]`, `[:eu]`, `[:eu :fr]`, `[:eu :de]`. Rules attach at
a level, and a person in
`[:us :ca]` is checked against every level that has rules, with the rest listed
in `:worklaw/unchecked`.

This exists because of a specific trap. **US federal law has no daily overtime;
California does.** A checker keyed on "US" that returned "compliant" for a
twelve-hour day would be confidently wrong for a worker in San Jose.

```clojure
(law/check twelve-hour-day [:us :ca] date-of {:period week})
;; => {:worklaw/coverage :partial :worklaw/checked [[:us]] :worklaw/unchecked [[:us :ca]]}
```

## Windows: a week cannot judge an annual cap

Rules carry a window — `:day`, `:week`, `:month`, `:year`, `:rolling-months`.
A rule whose window is longer than the period handed to `check` is **not
evaluated** and says so, with the reason:

| `:unevaluated/reason` | meaning | whose problem |
|---|---|---|
| `:window-longer-than-period` | seven days cannot judge 36協定's annual cap | inherent — no caller can fix it |
| `:missing-period` | no `:period` given | caller |
| `:missing-calendar` | no `:week-of` / `:month-of` given | caller |

Rules over `:month` count **statutory overtime**, not raw hours, which needs the
week and month a span falls in — so the caller supplies `:week-of` / `:month-of`
for the same reason it supplies `:date-of`. Overtime does not double-count:
daily excess first, then whatever weekly excess the remaining regular hours
produce (`statutory-overtime`). The baseline comes from the most specific level
that declares one, so a French week starts at 35h and a Japanese one at 40h.

## Rules that need a period say so

A week with Monday–Friday worked and nothing after it does not say whether the
weekend was a day off or simply outside the data. Guessing is wrong in a
different direction either way, so weekly rest is **not evaluated** without
`:period`, and says which rule it skipped:

```clojure
(law/check mon-to-fri [:jp] date-of)
;; => {:worklaw/coverage :full :worklaw/unevaluated [:jp-weekly-rest] :worklaw/violations []}
(law/compliant? that)   ;; => false
```

Related asymmetry, and the reason the edge gaps are computed separately:
**an edge gap may satisfy a rule, never violate one.** A window that happens to
open at midnight before an 09:00 shift shows a nine-hour leading gap that is an
artifact of where the query was cut, not a rest period anyone was denied.

## nil is not zero

`:worked/break-ms` **absent** means the source does not record breaks; a planned
roster says `09:00–17:00` and nothing about lunch. `:worked/break-ms 0` means it
does record them and there were none.

```clojure
(law/check [{:worked/start .. :worked/end .. :worked/ms ..}] [:jp] date-of opts)
;; => break rules land in :worklaw/unevaluated as :missing-break-data

(law/check [{... :worked/break-ms 0}] [:jp] date-of opts)
;; => :jp-break-45 fires
```

Asserting a missed break from a roster would claim to have seen something the
data never contained, and every full-day planned shift would read as unlawful.
`breaks-known?` is the predicate.

## Shipped rule sets

Six levels across three hierarchies, each rule carrying its provision and the date it was
recorded, so a reader can check it rather than trust it — and so a stale rule set
shows up as a stale date rather than as a confident answer.

| jurisdiction | source | rules |
|---|---|---|
| `[:jp]` | 労働基準法 | daily 8h (32条2項) · weekly 40h (32条1項) · break 45min over 6h / 60min over 8h (34条1項) · weekly rest 24h (35条1項) · **36協定**: 月45h/年360h 限度時間 (36条4項) · 特別条項 単月100h (36条6項2号) / 年720h (36条5項) / 2か月平均80h (36条6項3号) / 月45h超は年6回まで (36条5項) |
| `[:us]` | FLSA (federal) | overtime premium from 40h/week (29 U.S.C. §207(a)(1)) |
| `[:us :ca]` | Cal. Lab. Code / IWC | daily OT from 8h · double time from 12h (§510(a)) · meal 30min over 5h (§512(a), §226.7) · day of rest in seven (§551–552) · seventh consecutive day (§510(a)) |
| `[:eu]` | Directive 2003/88/EC | weekly 48h (Art. 6(b)) · daily rest 11h (Art. 3) · break over 6h (Art. 4) · weekly rest 24h (Art. 5) |
| `[:eu :fr]` | Code du travail | durée légale 35h (L3121-27) · daily 10h (L3121-18) · weekly 48h (L3121-20) · daily rest 11h (L3131-1) · weekly rest 35h (L3132-2) |
| `[:eu :de]` | ArbZG | daily 8h (§3) · break 30min over 6h / 45min over 9h (§4) · daily rest 11h (§5) |

A member state is a **sub-level of `[:eu]`**, not a bare country code: a French
worker is `[:eu :fr]` because the directive is the floor and the Code du travail
layers on top. `[:fr]` alone resolves to coverage `:none` — a bare code would
have to be guessed into a hierarchy, and this library does not guess.

Statutory **silence** is recorded too, so it is not left to be inferred:

```clojure
(law/absences [:us])
;; => [{:absent/kind :daily-hours-max
;;      :absent/note "federal law sets no daily hour cap and no daily overtime;
;;                    several states do"} ...]
```

Notes on what the shipped rules do *not* model are attached to the rules
themselves: the EU weekly cap is checked per single week where the directive
allows an averaging reference period (stricter, and said so); the JP weekly-rest
rule does not implement 4週4日の変形休日制; a directive binds member states, not
employers, and national transposition is often stricter.

## Prohibitions vs premiums

A finding carries `:violation/kind :overtime-due` when the statute prices the
hours rather than forbidding them. US overtime is lawful and expensive; a missed
rest period is not lawful at any price. Consumers are expected to route the two
differently — `cloud-itonami/kintai` blocks on prohibitions and escalates
overtime to a person.

## Maturity

| | |
|---|---|
| Role | capability |
| Dependencies | none |
| Tests | 38 tests, 185 assertions, all green |
| Jurisdictions | 6 levels across 3 hierarchies — anything else is `:none` or `:partial`, by construction |
| Runtime | `.cljc`, JVM + ClojureScript |
| Actor | `cloud-itonami/kintai` (勤怠) |

Adding a jurisdiction means adding a map with `:law/as-of` and a
`:rule/citation` on every rule; a test enforces both.

## Test

```bash
kbb -M:test
kbb -M:lint
```

## License

Apache-2.0.
