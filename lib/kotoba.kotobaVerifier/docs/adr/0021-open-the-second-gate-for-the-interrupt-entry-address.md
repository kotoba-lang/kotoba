# ADR 0021: Open the second gate for the interrupt entry address

## Status

Accepted.

## Decision

`kernel-isr-entry-address` is added to the four tables this namespace
re-derives:

1. `verify-expr!`'s privileged operation membership set
2. `verify-expr!`'s privileged arity map, at **1**
3. the target gate that confines kernel operations to the aiueos targets
4. `kernel-native?`, which suppresses the compile-time oracle

## Why all four, and why here at all

This namespace admits by MEMBERSHIP. An operation kotoba-sema, kotoba-kir,
kotoba-gmir and kotoba-native all admit still reaches the terminal `:else`
here and fails with `runtime KIR operation rejected` -- which is the two-gate
shape kotoba-kir's own file records for `string-contains?`: *both gates had to
open*. The break below shows exactly that message.

Arity **1** where every other address operation in this family is zero-arity,
and that asymmetry is why re-deriving the number is worth the duplication. A
zero-argument `kernel-isr-entry-address` would index the entry table with
whatever the previous expression left in the register, and the caller's next
act is to write the answer into an IDT gate descriptor. The failure is not a
crash; it is a jump to a plausible-looking address.

The three canned handler-address operations are pinned zero-arity in the same
test, so that widening one cannot be read as widening the family.

## What is landed here but not exercised here

Rows 3 and 4 need an ARTIFACT, and an artifact needs an emitter. This
repository pins kotoba-native deliberately (see `deps.edn`), and that pin
predates this operation's encoding, so a body containing it fails at `emit`
with a message that would still appear with the target rule deleted. Adding
such a case would be a green assertion that discriminates nothing -- the same
reasoning ADR 0020 records for the four firmware operations. Their gates are
exercised in amu, where the toolchain is pinned new enough.

**The kotoba-native pin is deliberately untouched.** Bumping it to today's tip
imports an unrelated allocator regression (8 failures in
`pinned-producer-lazily-spills-only-the-fifth-entry-argument`) belonging to
whoever owns that change, and nothing here needs a newer one.

## Evidence

`kbb -M:test`: 75 tests, 520 assertions, 0 failures (after merging kotoba-lang/main, which hoisted the fourth table into `kernel-native-operations`).

Two deliberate breaks, each producing the failure it names and no other:

| break | result |
|---|---|
| removed from the privileged membership set | `runtime KIR operation rejected` -- what the operation got before this change |
| the arity row changed from 1 to 0 | the admitted call is refused and the zero-argument call is admitted |
