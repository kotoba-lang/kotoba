# ADR-0051 — The watchdog was not it, and the ten failures are three classes

Date: 2026-08-18

## Status

Accepted as a measurement, **with its first conclusion corrected by ADR-0055**.
The classification stands. The refutation does not: it was the watchdog, and
this ADR measured the wrong deadline.

## Correction (2026-08-18, ADR-0055)

Everything below about `default-wall-deadline-ms` being 30,000 with three
orders of magnitude of headroom is true and irrelevant. The fixture declares
`:aiueos/schedule {:period-ms 3 :cycle-ms 1}` and `aiueos.manifest/normalize-schedule`
derives `deadline-ms (or (:deadline-ms sched) period-ms)` — so the wall
deadline for that component was **3 ms**, not 30,000. The default never
applied, because the manifest declared a schedule.

Captured in the failing run once the assertion was made to say why:
`:aiueos.execute/watchdog-exceeded {:deadline-ms 3, :elapsed-ms 7,
:terminated? true}`.

The 425 isolated boots that "refuted" it are also explained: they passed
because the execution fitted in 3 ms on a quiet machine. The measurement was
sound; the inference from it was not, and the number it should have read was
in the fixture rather than the default.

## The watchdog hypothesis is refuted

ADR-0050 recorded a suspicion: the suite's unstable twentieth failure — two
different `launcher-test` boots on two runs, at load average 99 — looked like
the bounded Chicory watchdog, whose deadline is wall-clock while this machine's
load is not.

Measured:

- **425 isolated `up-command` boots of the same fixture: 0 failures.** Timings
  1–708 ms, mean 16–98 ms depending on run, against a
  `default-wall-deadline-ms` of **30,000**. Three orders of magnitude of
  headroom.
- **400 of those in one JVM: 0 failures.** So it is not an accumulating fuel or
  quota budget within the boot path either — the other hypothesis worth
  ruling out, given ADR-0033 and ADR-0034 exist.
- A full suite run with a 40-boot probe appended, running last: **19 failures,
  probe clean.** The flake did not reproduce.

So the suspicion was wrong, and the honest state is smaller than either
version: **the twentieth failure is intermittent, unreproduced under direct
measurement, and its mechanism is unknown.** It is not the watchdog. Recording
that is worth more than the guess it replaces, because the guess would have
sent the next iteration to change a deadline that has three orders of magnitude
of room.

What stands from ADR-0050 is the narrower fact: **"the same nineteen" is a
number that holds when the machine is quiet**, and no ADR in this series should
quote it as though it were a constant.

## The ten failures are three classes, not one bug

The receipt now derives a cause per row from the verifier's own message, rather
than from a reading of it:

| class | count | what it is |
|---|---|---|
| `:native-slice-typed-values` | 6 | the object uses a typed value the `x86_64-aiueos-kernel-v1` slice does not admit — the wall `kotoba-kir`'s `only-native-word-typed-features?` describes |
| `:per-object-export-symbol` | 3 | the contract expects a symbol named after the object; the pinned compiler emits `kotoba_aiueos_probe` for **every** kernel object |
| `:native-slice-lowering` | 1 | admitted as a type, no lowering for the operation |

The export class is the one that looked cheapest and is not. `value-runtime-syscall-plan`
declares `(:export [aiueos-value-runtime-syscall-plan main])` and its contract
expects `kotoba_aiueos_value_runtime_syscall_plan`; the compiler produced
`kotoba_aiueos_probe`. Changing the contracts to match would give the 57
objects the UEFI path links **one symbol between them**. So this is upstream
work in `kotoba-lang/amu`, not a local edit — which is exactly the thing a
classification is for: it stops the next iteration from starting with the
cheapest-looking failure.

`:unclassified` is a class. A new failure mode surfaces as one rather than
being folded into an existing bucket, and the ratchet fails if a row carries it.

## Executable evidence

`aiueos.value-runtime-baseline-test`: **7 tests, 59 assertions, 0 failures**
(was 5/37). Full suite **621 tests, 9356 assertions, 19 failures** — the
baseline nineteen. Lint unchanged.

**Both directions, shown.** A histogram that does not sum to the failure count
fails only `the-causes-account-for-every-failure`; a row demoted to
`:unclassified` fails only `every-failure-is-classified`. Each mutation
asserted that the edit applied before running, after ADR-0050's first attempt
mutated nothing and read as a gate that could not discriminate.

## Remaining boundary

- **Nothing is fixed.** The ratchet reads ten and the classes say where the
  work is: six need native slice features, three need upstream export naming,
  one needs a lowering.
- **The intermittent twentieth failure has no mechanism.** The next attempt
  should capture it rather than reason about it — run the full suite in a loop
  and print the failing boot's result map when it happens, instead of probing
  the path in isolation, which is what did not reproduce it.
