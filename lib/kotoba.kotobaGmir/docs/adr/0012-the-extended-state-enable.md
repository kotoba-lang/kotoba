# ADR 0012: The extended state enable

## Status

Accepted.

## Decision

Add three actions to `x86-privileged-action-arities`:

| action | arity | instruction |
|---|---|---|
| `:read-cr4` | 0 | `mov r64, cr4` |
| `:write-cr4` | 1 | `mov cr4, r64` |
| `:xsetbv` | 2 | `xsetbv` (index in ECX, value in EDX:EAX) |

## Why, when `:xgetbv` already exists

ADR 0009 added the READ half of a feature check and said, in its own "what this
table cannot say" section, that `xgetbv` raises `#UD` unless `CR4.OSXSAVE` is
set. It did not say who sets it. Until now the answer was **a C function** —
`prepare_bsp_extended_state()` in the aiueos kernel — because this table named
CR0 and CR3 and stopped.

That gap is not theoretical. Measured 2026-09-02 under QEMU TCG with `-cpu max`:
`cpuid` reports AVX and AVX2, and `CR4.OSXSAVE` is **clear**, because nothing in
a pure-Kotoba kernel can set it. The guard therefore refused the AVX2 arm on a
machine that has AVX2 — correctly, and with no way for the guest to fix it. A
`kernel-dot-f32` probe that exists to compare the two arms exercised one of them
twice.

## Why these arities

None of the three is invented.

`:read-cr4` and `:write-cr4` take what `:read-cr0` and `:write-cr0` take. A
control register is one machine word, read whole and written whole; CR4 differs
from CR0 only in which bits mean what. The ones that matter here are OSFXSR (9),
OSXMMEXCPT (10) and OSXSAVE (18).

`:xsetbv` takes what `:write-msr` takes — `(index, value)`, index in ECX and
value split across EDX:EAX — because at the machine level it is `wrmsr` with a
different opcode. Arity 2 rather than 1: XCR0 is index 0, but the architecture
reserves an index space, and an `xsetbv` whose index was whatever the previous
expression left in ECX would write a register nobody named.

## There is no `:write-cr2`

CR2 is written by the CPU when a page fault is taken; a kernel that wrote it
would be lying to its own handler about the faulting address. `:read-cr2` stays
alone, and the test asserts the absence rather than merely leaving it out.

## What this table cannot say

Two things, both of the kind ADR 0009 already named.

**A sequence.** `xsetbv` requires `CR4.OSXSAVE` already set — it raises `#UD`
otherwise, which in a kernel is a self-inflicted fault in the middle of feature
detection. So the order is `cpuid` leaf 1 ECX bit 26 (XSAVE) → set CR4.OSXSAVE →
`xsetbv` → `xgetbv`. This table describes one action at a time.

**A value.** `xsetbv` raises `#GP` when the value sets a bit XCR0 does not
define, when bit 0 (x87 state) is clear, or when bit 2 (YMM) is set without bit
1 (SSE). Arity checking cannot see any of that: `(kernel-xsetbv 0 6)` and
`(kernel-xsetbv 0 4)` have the same shape and the second faults. The operand is
frequently not a literal at all — the working spelling is
`(kernel-xsetbv 0 (bit-or (kernel-xgetbv 0) 6))`, whose value is a property of
the machine.

Both live in `kotoba-native` `docs/avx2-guard-sequence.md` with the rest of the
sequence.

## Evidence

`kotoba.gmir-test/cr4-and-xsetbv-are-the-write-half-of-the-feature-check`: each
of the three validates at its declared arity and is refused one argument either
side of it; CR0/CR2/CR3, the MSR pair and `:xgetbv` are pinned at their own
arities beside them so a change that widened the whole family fails here.

Shown to discriminate by deleting `:xsetbv 2` from the table: the arity
assertion fails with `{:read-cr4 0, :write-cr4 1}` and the two-argument program
fails validation with `GMIR rejected: invalid-x86-privileged`. Restored, 24
tests / 273 assertions, 0 failures.

Nothing here executes. GMIR owns the arity contract; the encodings
(`41 0f 20 e2`, `41 0f 22 e2`, `0f 01 d1`) live in `kotoba-native`.
