# ADR-0059 — The instrument had the defect it was built to find

Date: 2026-08-18

## Status

Accepted. The upstream reproduce command is verified to work for someone who
is not us, and the receipt now dates itself from a clock instead of from a
string literal.

## Why replicate

[amu#625](https://github.com/kotoba-lang/amu/issues/625) tells a maintainer to
clone this repository and run one command. If that command does not work from a
clean checkout, **the ask is dead on arrival and nobody would tell us** — they
would try it once and move on. Nine iterations of measurement rest on an
instrument that had only ever been run in the tree that grew it.

## What the replication says

A fresh `git clone` of `kotoba-lang/aiueos`, running the issue's command
verbatim:

```
11 objects, 11 failing -> qualification/value-runtime-baseline.edn
```

and `git diff --quiet` on the produced file: **identical to the committed
receipt, byte for byte**. The command resolves the compiler pin, finds the
scripts on the classpath, and reproduces every row. The upstream ask is
actionable by a third party.

## What the replication found

`:value-runtime/measured-at` was **a string literal**, `"2026-08-18"`, written
into the runner. A run in any later year would have produced a receipt claiming
it was measured today — **a field reporting something it had not measured**,
which is the exact defect class every iteration of this series has been finding
elsewhere, sitting in the instrument used to find it.

It read correctly in the replication for the worst reason: the literal happened
to match the day. A byte-identical receipt from a fresh clone was evidence of
reproducibility *and* camouflage for a constant.

## Decision

**The date comes from the clock**: `(str (java.time.LocalDate/now))`.

A consequence worth stating: the receipt is no longer byte-identical across
days, and the replication evidence above is dated rather than permanent. That
is the right trade — the date is metadata about *when* the measurement happened,
and the findings (rows, causes, forms, counts) remain exactly reproducible.
A receipt that reproduces byte-for-byte forever is one that has stopped saying
when.

**The date is checked, not just written.** `the-receipt-dates-itself-from-a-clock`
requires an ISO date that is not in the future — a receipt from the future is a
broken clock or a hand-edit, and both mean the numbers beside it are unowned.

## Executable evidence

`aiueos.value-runtime-baseline-test`: **12 tests, 83 assertions, 0 failures**.
Full suite **629 tests, 9390 assertions, 19 failures** — the baseline nineteen.
Lint unchanged.

**Both directions**: dating the receipt `2031-01-01` fails the future check with
the date printed; replacing it with `"sometime"` fails both the format and the
comparison. Each mutation asserted its edit applied before running.

## Remaining boundary

- **Only this receipt was audited.** Other fixed strings in this repository that
  claim to describe a measurement have not been looked for, and the same
  question — *does this field report what the run actually observed?* — applies
  to every one of them.
- The eleven failures are unchanged: five on `kernel-compare-exchange-u32`,
  three on [#626](https://github.com/kotoba-lang/amu/issues/626), two on the
  capability table, one lowering.
- **Neither issue has an answer yet**; both carry one comment, and both
  comments are ours.
