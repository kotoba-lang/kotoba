# ADR: Open the second gate for the general atomics and the system operations

## Status

Accepted.

## Context

kotoba-gmir ADR 0007 adds twelve operations; kotoba-kir, kotoba-sema,
kotoba-mir, kotoba-codegen and kotoba-native all admit them.

**This namespace would still have refused every one of them.** It re-derives
its own kernel operation tables rather than importing the frontend's, and it
admits by MEMBERSHIP -- an operation absent from them reaches the terminal
`:else` and fails with `runtime KIR operation rejected`, regardless of what the
compiler admitted.

That is the same two-gate shape kotoba-kir's own file records for
`string-contains?`: *"this clause ALONE unlocks nothing -- the same two
operations are refused a second time by `kotoba.verifier/string-operations`,
which re-derives its own table. Both gates had to open."*

Measured against the sha `kotoba-lang/amu` pins today (`58a02b4`): all twelve
were absent from all four tables here.

## Decision

The twelve join all four:

1. `verify-expr!`'s kernel-memory family, with the arities -- **four for the
   adds and swaps, five for the compare-exchanges.** This is the reason the
   table is re-derived rather than imported: an emitter handed a four-argument
   compare-exchange would take the replacement as the comparand and store
   whatever the register happened to hold.
2. `verify-expr!`'s kernel-privileged family, all six zero-arity. A
   one-argument `kernel-fence-full` would emit `mfence` and silently discard
   whatever the caller thought it was ordering.
3. The target gate that confines kernel operations to the aiueos kernel
   targets. **The lock pair was missing from this one too** and is added with
   them.
4. `kernel-native?`, which suppresses the compile-time oracle. An atomic
   read-modify-write and an `rdtsc` are not compile-time values. **The lock
   pair was missing here as well.**

## Pins are deliberately untouched

Neither the `kotoba-kir` nor the `kotoba-native` pin moves. Nothing in this
change needs a newer one -- the tables are literal symbol sets, checked before
any backend is called -- and bumping the native pin to today's tip was tried
and imports an unrelated allocator regression
(`pinned-producer-lazily-spills-only-the-fifth-entry-argument`, 8 failures)
that belongs to whoever owns that change. A correctness fix should not carry
someone else's red.

## Evidence

`kbb -M:test`: 61 tests, 323 assertions, 0 failures.

Break shown: removing the six atomics from the memory family returns them to
`runtime KIR operation rejected` -- which is what they got before this change,
and the reason it exists.

A third test asserts the floor the other two stand on: a misspelled
`kernel-cmpxchg-u16` is still refused by absence, so "admitted" here means
membership rather than a permissive fallthrough.
