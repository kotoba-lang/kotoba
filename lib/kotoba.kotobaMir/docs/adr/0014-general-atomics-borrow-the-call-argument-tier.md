# ADR 0014: The general atomics, and where a five-operand instruction gets its fifth register

## Status

Accepted.

## Context

kotoba-gmir ADR 0007 adds six general atomic read-modify-writes:
`kernel-atomic-add-u32/u64`, `kernel-xchg-u32/u64` and
`kernel-cmpxchg-u32/u64`. MIR has to select and allocate them.

Five of them fit the store's shape -- `base length index stored` in, one value
out. The two compare-exchanges do not: they carry a guest-supplied comparand
as well, so **five values must be live at the instruction**, and the
conservative all-vreg path has a four-register scratch tier.

## Decision

**Select and validate all six the way the lock pair is selected and
validated.** The ceiling is 4096 and nothing else. The index must be a
register. `:mir/expected` is added to the generic operand check and, critically,
to `instruction-sources`.

**The compare-exchanges borrow the call-argument tier on the conservative
path.** `physical-register?` already admits it, and `allocate-with-spills`
already hands that exact tier to a five-argument call. Nothing lives across the
instruction -- every operand is loaded from its spill slot immediately before
and is dead immediately after -- so borrowing cannot collide with a call's own
use of the tier.

On x86-64 that tier is `rdi rsi rdx rcx r8` and **deliberately excludes RAX**,
which `lock cmpxchg` fixes as its comparand register and which the encoder
saves and restores regardless.

The scratch tier is not widened. Widening it would change allocation for every
program in the repository to serve two instructions.

## Evidence

`kbb -M:test`: 86 tests, 1522 assertions, 0 failures.

Three deliberate breaks, each producing the failure it names and no other:

- assigning the compare-exchange four scratch registers instead of five
  (`c4 = c0`) -> `(not (= 5 4))` at the distinct-register assertion;
- deleting `:mir/expected` from `instruction-sources` -> the comparand missing
  from the source set;
- deleting MIR's own ceiling check -> the direct-MIR ceiling assertion.

**The third break is the one worth recording, because the first version of that
test did not catch it.** Asserting the ceiling through `select-target` proves
nothing about MIR: GMIR validates first and rejects the same instruction, so
MIR's check could be deleted entirely and the suite stayed at 0 failures. The
test now hands `mir/validate!` a MIR program directly, and keeps the GMIR route
as a separate, clearly-labelled assertion about the earlier layer.

The same misreading nearly landed for `:mir/expected`: an allocation test
looked like it would catch a missing liveness source and did not, because the
conservative path assigns fixed registers and the scanner path had slack. That
contract is now asserted on `instruction-sources` directly.

## Does not decide

No encoding. The bytes are kotoba-native's, on both ISAs.
