# ADR-0055 — A three-millisecond deadline is a test of machine load

Date: 2026-08-18

## Status

Accepted and executable. The intermittent suite failure has a mechanism, a
receipt, and a fix. ADR-0051's refutation of the watchdog hypothesis is
corrected in place.

## What it was

`aiueos.launcher-test`'s fixture declares
`:aiueos/schedule {:period-ms 3 :cycle-ms 1}` to test *cycle* arithmetic — a
component due at cycles 0, 3, 6. `aiueos.manifest/normalize-schedule` derives

```clojure
deadline-ms (max 1 (or (:deadline-ms sched) period-ms))
```

so a manifest that declares a schedule and omits `:deadline-ms` **gets its
period as its wall deadline**. The fixture was therefore executing Chicory
under a **3 ms** deadline, and the `default-wall-deadline-ms` of 30,000 never
applied, because the default only covers manifests with no schedule at all.

Captured, in the run where it happened:

```clojure
:aiueos.execute/watchdog-exceeded {:deadline-ms 3, :elapsed-ms 7, :terminated? true}
```

That also explains ADR-0051's 425 clean isolated boots: they fitted in 3 ms on
a quiet machine. **The measurement was sound and the inference from it was
wrong** — it read the default rather than the fixture's own derived deadline,
and concluded "not the watchdog" from a number that was never in play.

## How it was caught

Not by reasoning harder. **By making the assertion say why.**

`(is (= 2 (count (:aiueos/boot-results result))))` fails with *expected 2, got
1*, which names the symptom and nothing else — while the result map already
contained the component that stopped, its decision, and the execution flag that
fired. A `boot-summary` message on the seven boot assertions renders exactly
that, and the flake explained itself **on the first run after the change**,
after three iterations of it being unreproducible.

That is the same defect this loop has been finding everywhere else, one level
in: a check that reports less than it knows.

## Decision

**The fixture declares `:deadline-ms 5000`.** What it tests is cycle
scheduling; inheriting a 3 ms wall deadline from `:period-ms` was never
intended, and a 3 ms deadline on a machine whose load is not controlled is not
a test of scheduling, it is a test of machine load.

**The product is left alone.** "A task due every 3 ms that takes longer than
3 ms is overrunning" is a defensible rule for a control loop. The sharp edge
worth knowing repo-wide is that **`:period-ms` silently becomes your wall
deadline** when `:deadline-ms` is omitted — quiet, correct, and surprising.

**The diagnostic message stays.** It is worth more than the fix: the next
execution limit to fire in these tests will name itself too.

## Executable evidence

- **Before**: `up-command-boots-the-periodic-component-again-at-its-next-due-cycle`
  failed with the watchdog receipt above, on the first run after instrumenting.
- **After**: `aiueos.launcher-test` three consecutive runs, 20 tests, 44
  assertions, 0 failures.
- Full suite **625 tests, 9371 assertions, 19 failures** — the baseline
  nineteen, now expected to be stable rather than load-dependent.
- Lint unchanged.

The after-evidence is a causal argument, not a count: the mechanism is named in
the receipt and the fix removes it. Three passes do not prove a probabilistic
failure is gone; a 5,000 ms budget for work measured at 7 ms does.

Other `:aiueos/schedule` maps without `:deadline-ms` were checked — the rest
are in `manifest_test`, which calls `normalize-schedule` and executes nothing,
so no watchdog runs against them.

## Remaining boundary

- **The value-runtime ten are untouched** and still split across
  [amu#625](https://github.com/kotoba-lang/amu/issues/625) and
  [#626](https://github.com/kotoba-lang/amu/issues/626).
- **Nothing prevents the next fixture from inheriting a millisecond deadline.**
  A rule — "a manifest that executes wasm in a test declares its deadline" —
  is not enforced anywhere, and this ADR does not add a gate for it.
