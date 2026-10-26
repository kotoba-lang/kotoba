# ADR-0050 — The value runtime is checked by eleven scripts nobody runs

Date: 2026-08-18

## Status

Accepted as a measurement. It fixes no Kotoba object. It replaces twelve
undifferentiated red assertions with one receipt that says what is actually
wrong, and a ratchet that stops the number growing.

## Context

`aiueos.kotoba-object-reachability-test` has been failing twelve assertions —
the whole `value-*` family, "compiled by no script and not listed in
`not-built-here`". Twelve of the suite's nineteen standing failures. The
obvious repair is to add twelve entries to `not-built-here`, whose contract is
*say what does execute it*.

Measured before writing any:

- **Eleven `verify_value_*.clj` scripts exist** in `os/aiueos/scripts/aiueos/`,
  each compiling one object with `kotoba.compiler.core` and checking it against
  its `contracts/*-v1.edn`.
- **Nothing in the repository invokes any of them.** No task, no script, no
  test, no doc mentions them — `grep` across every `.edn`, `.sh`, `.cljs`,
  `.clj`, `.md` and `.yml` outside that directory returns nothing.
- The reachability gate could not have seen them: it reads
  `(.listFiles scripts-dir)` filtered to `.isFile`, which is one directory
  deep, and these are one level below.
- **Invoked by hand, ten of ten fail.** `operation has no admitted type
  signature` (six), `operation has no admitted lowering`, `native export
  mismatch` (two), `planner object export is not exact`.

So the twelve reds were pointing at something true, and the tidy repair would
have buried it: writing "verified by `verify_value_*.clj`" would have been
false in the way that matters — those scripts do not run, and when they do,
they fail.

## Decision

**Do not touch the reachability gate.** Its red is correct. An object earns its
`not-built-here` entry when something actually executes it, and today nothing does.

**Invoke the verifiers and write down what happened.**
`aiueos.verify-value-runtime-all` runs all ten with the argument vectors their
own usage strings ask for — recorded rather than guessed, because passing the
wrong number of arguments reports a usage error as a failing object, which is
how the first pass of this measurement produced four false failures.

It emits `qualification/value-runtime-baseline.edn`, a receipt naming **the
compiler sha it measured against**. A count without its closure is a number
that cannot be rechecked.

**Ratchet, not gate.** `aiueos.value-runtime-baseline-test` asserts the receipt
still describes this repository — same compiler sha as `deps.edn`, every
`value-*.kotoba` either measured or named as an input to something that is, the
headline count derived from the rows rather than asserted beside them, a
failure count that has not grown, and an evidence floor so a receipt of nothing
cannot read as clean. Landing ten more permanently-red assertions would have
added noise to a suite that already has nineteen; a ratchet turns one way and
goes green by being improved.

Two objects have no verifier of their own — `value-runtime-sha256` and
`value-runtime-digest-equal` — because they are *inputs* to the ones that do.
Covered, not missing. One verifier has no source:
`verify_value_runtime_kernel_image.clj`. Recorded rather than deleted, because
which of the two is the missing half is not something this run can know.

## The suite's "nineteen" is not stable

Running the full suite with these three files added produced **twenty**
failures twice, and **a different twentieth each time**:
`up-command-defaults-to-cycle-zero-booting-everyone`, then
`up-command-boots-the-periodic-component-again-at-its-next-due-cycle`. The same
tree without them produced nineteen. `aiueos.launcher-test` alone passes.

The load average during these runs was **99**. Both failures are
`up-command` booting two components and getting fewer back. No `Thread/sleep`
is involved and the cycle is passed explicitly, so the schedule is not the
clock-dependent part; the suspect is the bounded Chicory interrupt watchdog,
whose deadline is wall-clock while the machine's load is not controlled.

**That is a suspicion, not a measurement.** What is measured is that the
baseline everyone in this ADR series has been quoting — "the same nineteen" —
is a number that holds when the machine is quiet. Confirming the mechanism, and
making the deadline something other than wall-clock, is the next thing this
loop should do.

## Executable evidence

- `aiueos.verify-value-runtime-all`: **10 objects, 10 failing**, receipt written.
- `aiueos.value-runtime-baseline-test`: **5 tests, 37 assertions, 0 failures.**
- **Both directions, shown** — and the first attempt at showing them failed:
  two mutations reported no discrimination because the edit never applied
  (`pprint` writes the receipt as a namespaced map `#:value-runtime{…}`, so the
  search string was absent). Re-run with an assertion that the file actually
  changed, a stale compiler sha fails only
  `the-receipt-is-about-the-compiler-this-repo-pins`, and a headline count that
  disagrees with its rows fails only `the-failure-count-has-not-grown`.
  A mutation that does not apply looks exactly like a gate that does not
  discriminate.
- `kbb -M:tcb-check` `{:valid? true :files 39 …}`. Lint unchanged.

## Remaining boundary

- **Ten objects still do not compile.** Nothing here fixes one. The value
  runtime is source that no longer builds against the pinned compiler, and
  whether the objects or the compiler moved is not known.
- **The verifiers are still not in any automated run.** Invoking them needs the
  compiler closure, which is a test-only dependency; the ratchet checks the
  receipt rather than regenerating it, so a receipt can only go stale by the
  compiler pin moving — which is exactly what the sha assertion catches.
- **The `value-*` objects are not in the TCB inventory.** They are the value
  runtime — capability tables, dispatch, domain — and the inventory covers
  `src/aiueos/*` only.
