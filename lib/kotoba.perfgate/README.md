# kotoba-lang/perfgate

**T5 assurance — the gate a performance claim has to pass before anyone may act on it.**

[`layout`](https://github.com/kotoba-lang/layout),
[`traversal`](https://github.com/kotoba-lang/traversal),
[`paging`](https://github.com/kotoba-lang/paging) and
[`ioplan`](https://github.com/kotoba-lang/ioplan) all produce plans with printed
cost models. **A model is an argument, not a measurement**, and the gap between
the two is where optimization fossils come from: a number that was true on the
machine someone benchmarked once, kept as a constant, and quietly wrong
everywhere after.

```clojure
(g/qualify candidate baseline)
;=> {:qualified? true :improvement 0.2 :separation {:gap 20.0 :summed-stdev 2.29 …}}
```

## Six refusals

| refusal | why |
|---|---|
| `:insufficient-samples` | fewer than the policy demands |
| `:too-noisy` | relative standard deviation above tolerance |
| `:no-baseline` | "fast" is not a property of a single measurement |
| `:not-separated-from-noise` | the gap is smaller than the arms' own spread |
| `:machine-mismatch` | the arms ran on different hardware, so the difference between them is not the change you made |
| `:metric-mismatch` | wall time compared against cache misses |
| `:provenance-too-weak` | the machine descriptor is `:assumed` — nobody read those numbers off a device |

The one worth dwelling on is **`:not-separated-from-noise`**, because it fires
on results that look convincing:

```clojure
;; baseline [100 90 110 95 105]   candidate [94 88 100 90 98]
{:improvement 0.06                      ; a 6% win!
 :qualified? false
 :reasons [{:reason :not-separated-from-noise :gap 6.0 :summed-stdev 13.0}]}
```

Six percent, comfortably above the 5% threshold, and entirely inside the noise.
Reporting the ratio without this check is exactly how a benchmark becomes
folklore. The ratio is still reported — hiding it would be its own dishonesty —
but it does not qualify.

## The statistics are modest and say so

Mean, sample standard deviation (n−1), median, p95. The separation test is
"the gap exceeds the summed standard deviations" — **a stated heuristic, not a
p-value**. Claiming a significance test this does not implement would be the
same failure one level up.

A single sample reports `:stdev 0.0`, which is honest — one measurement carries
no information about its own spread — and the gate refuses it regardless.

## An unqualified result gets no artifact

```clojure
(g/claim (g/qualify weak-candidate baseline) …)
;=> throws: refusing to seal an unqualified result
```

Not a record marked `:qualified? false`. Such a record ends up in a slide deck
within the week.

A sealed claim carries a fingerprint over its own contents, so `verify-claim`
catches an edited sample *or* an edited headline number, and re-runs the
verdict — a claim that no longer qualifies under its policy is not a claim.

## The part that actually retires an optimization

```clojure
(g/applicable [claim] current-machine)
;=> {:applicable []
;    :stale [{:claim/plan-id :soa-particle :measured-on "fixture-a"
;             :reason :machine-changed}]}
```

A claim records the fingerprint of the machine it was proved on. Change one
cache geometry — or one core count — and it stops applying. Run this at startup
and a system carries its own list of retired optimizations instead of
accumulating fossils, which is the only mechanism here that works without
anybody remembering to look.

## Policy is a value

```clojure
{:policy/min-samples 5
 :policy/max-relative-stdev 0.10
 :policy/min-improvement 0.05
 :policy/require-provenance :measured
 :policy/require-baseline? true}
```

Every threshold can be relaxed deliberately and per call — that is the point of
it being a policy rather than a constant — and the relaxation is recorded in
the claim as `:claim/policy-id`.

## Test

```sh
kbb -M:test
```

Pure `.cljc`. Depends only on
[`kotoba-lang/machine`](https://github.com/kotoba-lang/machine). See
ADR-2608030200 in the superproject.
