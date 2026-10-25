# ADR 0023: Open the second gate for the f32 dot product

## Status

Accepted.

## Decision

`kernel-dot-f32` (kotoba-gmir ADR 0010) is added to the two tables this
namespace re-derives for it:

1. `kernel-memory-arities`, at **5**
2. `kernel-native-operations`, which suppresses the compile-time oracle

## Why here at all

This namespace admits by MEMBERSHIP. An operation that kotoba-sema, kotoba-kir,
kotoba-gmir, kotoba-mir, kotoba-codegen **and** kotoba-native all admit still
reaches the terminal `:else` here and fails with
`runtime KIR operation rejected`. That is the two-gate shape ADR 0021 recorded
for `kernel-isr-entry-address` and kotoba-kir's own file records for
`string-contains?`: *both gates had to open*.

This one was not found by reading. Six repositories had landed the operation
with green suites, and the first real `.kotoba` program that used it —
`os/aiueos/native/dot-f32-probe.kotoba`, written to run it under QEMU — failed
here.

## Arity 5, re-derived

Getting the arity wrong here is worse than for the compare-exchanges beside it.
Four of the five arguments are **interchangeable i64 words at this layer** —
two bases and two lengths — so a short call does not fail on a type. It
silently takes a length as a base and folds whatever is at that address.

That is the same argument the existing comment makes for the compare-exchanges,
one degree stronger, and it is why the number is data here rather than a shared
constant.

## Why it is not in `kernel-memory-operations`

That table is `op -> arity` for operations shaped `base length index [value]`,
and every member of it inherits both the arity check and the oracle
suppression by being in it. `kernel-dot-f32` is shaped
`a-base a-length b-base b-length count` — two regions, no index — so it does
not arrive with that table and has to be named in both places separately. The
test asserts both halves of that: it is in `kernel-native-operations` and it is
**not** in `kernel-memory-operations`.

## The oracle row

`kernel-native-operations` decides whether the ORACLE re-executes an entry, and
the same decision is made independently in `kotoba.kir/lower`. The existing
comment on that var says what a disagreement costs, and it applies unchanged
here: the compiler correctly seals no value, this side re-executes the entry,
gets `:kernel-memory-unavailable`, and refuses the artifact as an oracle
mismatch it never had.

## Evidence

`kbb -M:test -n kotoba.verifier-test`: 66 tests / 420 assertions, 0
failures (was 63 / 411).

Removing both rows again turns all three new tests red by name:

- `the-f32-dot-product-is-admitted-at-arity-five` — with the literal message
  `runtime KIR operation rejected`, which is the two-gate shape itself
- `the-f32-dot-product-pins-arity-five-independently` — the three short/long
  calls stop being rejected *by arity* and start being rejected by absence
- `the-f32-dot-product-suppresses-the-compile-time-oracle` — membership

## `kernel-xgetbv` was in the same condition, and nobody had noticed

While the probe was being written it also called `kernel-xgetbv`, to report the
AVX2 guard's own inputs so that "both arms agree" could not be an agreement
between a sequence and itself. That failed here too, with the same message.

`kernel-xgetbv` had been landed in kotoba-gmir, kotoba-kir, kotoba-sema and
kotoba-native, with a whole ADR each, and never here. It joins the four
privileged tables at arity **1** — the XCR index — where the `cpuid` four
beside it take two, which is exactly why the number is re-derived rather than
shared.

Two operations, two streams, the same gate, found by the same thing: a program.

## What is landed here but not exercised here

The end-to-end proof is an artifact, and it lives in aiueos: the probe compiles
through this gate and runs under QEMU TCG. This repository pins kotoba-native
deliberately, and this operation's encoding is newer than that pin, so a body
containing it cannot reach `emit` here. The membership tests above are what
this repository can assert about it.
