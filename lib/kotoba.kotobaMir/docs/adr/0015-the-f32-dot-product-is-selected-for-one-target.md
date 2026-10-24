# ADR 0015 — The f32 dot product is selected for one target

Status: accepted (2026-09-02)

## Context

kotoba-gmir ADR 0010 declares `:gmir/kernel-dot-f32`: two f32 regions, one
element count, one i64 result carrying the binary32 pattern of the sum. This
layer has to answer three questions about it that GMIR deliberately does not.

## Decision

**It selects for x86-64 and refuses every other target**, with its own
rejection reason `:x86-simd-target-mismatch` rather than the privileged
channel's `:x86-privileged-target-mismatch`. The reason has to be its own,
because the *argument* is not the privileged one. Control registers and port
I/O are facilities AArch64 does not have. AArch64 does have SIMD — it has NEON,
and it would answer the same question with a different reduction order.

Order is the whole contract of this operation: the x86 emitter's AVX2 arm and
its scalar arm are required to produce bit-identical results, so a second
backend is not free to reduce its lanes in whatever order its instructions
suggest. An AArch64 spelling is a decision about *which* tree, made where
someone needs it, and it is not a translation of this one.

**It borrows the call-argument tier in the conservative all-vreg path**, the
way the compare-exchanges do (ADR 0014). Five values are live at once — two
bases, two lengths, a count — against a four-register scratch tier. The
argument that made that safe for `cmpxchg` holds unchanged here: nothing lives
across the instruction, because every operand is loaded from its slot
immediately before it and is dead immediately after.

There is one thing to add to that argument, and it belongs at this layer even
though it is about the encoder. The emitted sequence touches general registers
that are *not* its operands: RAX, RCX and RDX, which `cpuid` writes
unconditionally, and RBX, which `cpuid` writes and which is callee-saved. It
pushes and pops all four itself. It has to, and not because of a convention:
`saved-registers` derives a function's frame saves from a `tree-seq` over the
*instruction maps*, so a register a byte sequence clobbers without naming is a
register nothing saves.

**It is not schedulable.** `schedulable-integer-operations` is a set of pure,
non-trapping integer operations, and this is none of the three. Admitting it
would let a reordering move a value across a sequence that pushes and pops four
general registers and branches on a feature bit.

## Consequences

`instruction-sources` lists all five operand keys. That is the entry a bug
hides behind: a field missing there is a value the allocator believes is
already dead, and an allocation test only *exhibits* the resulting corruption
on a program whose pressure happens to force the reuse. The test asserts the
function directly for that reason — and the measurement below shows the
allocation test catching it anyway on the exhausted-tier program, which is luck
worth having and not a substitute.

MIR re-derives the ceiling check rather than trusting GMIR's. Going through
`select-target` does not test it: GMIR validates first and rejects the same
instruction, so a deleted MIR check leaves that route green. The ceiling
*value* is GMIR's own var rather than a transcription, so only the check is
duplicated, not the number.

## Verification

`kbb -M:test`: 95 tests / 1962 assertions, 0 failures (was 89 / 1933).

Every new gate was shown to discriminate. Deleting all three at once — the
liveness keys, the target rejection and the ceiling check — turns exactly four
tests red by name:

- `simd-dot-is-x86-only` (both assertions)
- `simd-dot-pins-its-ceiling-in-mir-itself` (all four ceilings)
- `simd-dot-reads-all-five-of-its-operands` ("both bases, both lengths and the
  count are all read")
- `simd-dot-allocates-under-an-exhausted-scratch-tier` — which is the liveness
  break *exhibiting itself*: with three sources dropped from the scan the
  allocator reused their registers and the five sources stopped being distinct.
