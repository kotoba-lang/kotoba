# ADR-0056 — Omitting a deadline does not mean no deadline

Date: 2026-08-18

## Status

Accepted and executable. It closes the last gap ADR-0055 named: nothing stopped
the next fixture from inheriting a millisecond wall deadline.

## Context

ADR-0055 fixed one fixture and said plainly that the rule it violated was
enforced by nothing. Measuring the derivation again while writing the gate made
it sharper than that ADR stated:

```clojure
cycle-ms    (or (:cycle-ms sched) 1)      ; default-cycle-ms is 1
period-ms   (or (:period-ms sched) cycle-ms)
deadline-ms (or (:deadline-ms sched) period-ms)
```

So it is not only `:period-ms` that becomes the wall deadline. **Any manifest
that declares a schedule and omits `:deadline-ms` gets a millisecond-scale
budget — its period, or 1 ms if it named no period either.** A schedule of
`{:priority 0}` executes under a 1 ms deadline. `default-wall-deadline-ms`
(30,000) never applies to any of them, because that default is only for
manifests with no schedule at all.

## Decision

**Every `:aiueos/schedule` in `test/`, `examples/` and `resources/` declares
its own `:deadline-ms`**, or its file is named with the reason it need not.

The derivation is not changed. "A task due every 3 ms that takes 7 ms is
overrunning" is a defensible rule for a control loop, and a repo-wide edit to
the default would be a product decision made to quiet a test. What the gate
requires is that the number be **written down**, because the surprising part is
that omitting it does not mean "no deadline".

Two exemptions, each a claim about the file:

- `manifest_test.cljc` — the tests *of* the derivation. They assert what
  `normalize-schedule` produces from a schedule with no `:deadline-ms`, which
  is the behaviour this gate exists to make visible. Nothing there executes.
- `contract_test.cljc` — contract validation, including a deliberately
  misspelled `:deadline_ms` negative fixture and a `{:priority 0}` schedule
  with no timing at all. Checked as data; no manifest there reaches
  `aiueos.execute`.

A third names the gate's own source, whose docstring quotes schedule maps as
prose. Listed rather than skipped silently, so the scan has exactly one kind of
hole.

**The exemptions are checked too**: a named file must exist, must carry a
reason of real length, and must still contain a bare schedule — an exemption
that outlived its subject turns the list into decoration.

## Executable evidence

`aiueos.schedule-deadline-test`: **3 tests, 10 assertions, 0 failures**. Full
suite **628 tests, 9381 assertions, 19 failures** — the baseline nineteen.
Lint unchanged.

**Both directions, shown**, each mutation asserted to have applied first:

- removing ADR-0055's `:deadline-ms 5000` from the launcher fixture makes the
  gate name the file, the line and the map — it would have caught that bug;
- pointing the scan at a directory that does not exist fails
  `the-scan-found-something` with *only 0 literals found*, rather than
  reporting clean. A scan that reads nothing must not pass, and that is the
  failure mode this whole loop keeps finding.

The brace matching is balanced rather than regex-terminated: a nested map
inside a schedule would otherwise be read as its end, and the gate would go
quiet on exactly the complicated cases.

## Remaining boundary

- **`src/` is not scanned.** No `:aiueos/schedule` literal lives there today,
  and a manifest built programmatically would not be caught by a text scan in
  any directory. This gate catches literals, which is what the incident was.
- **It cannot tell execution from validation.** That is what the exemption
  reasons are for, and they are prose that a reader has to keep true.
- The value-runtime ten are untouched
  ([#625](https://github.com/kotoba-lang/amu/issues/625),
  [#626](https://github.com/kotoba-lang/amu/issues/626)).
