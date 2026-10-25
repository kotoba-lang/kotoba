# ADR 0008: The write half of a feature check

## Status

Accepted.

## Decision

Admit three privileged operations in `kernel-privileged-operations`:

| spelling | arity | meaning |
|---|---|---|
| `(kernel-read-cr4)` | 0 | CR4 as one machine word |
| `(kernel-write-cr4 value)` | 1 | write it whole |
| `(kernel-xsetbv index value)` | 2 | write XCR[index] from `value` |

They join `reserved-function-names` by derivation, so a guest cannot shadow one
with a `defn` of its own and get past the arity check that way.

## Why

ADR 0003 admitted `kernel-xgetbv` and said, in its own "what this cannot check"
section, that `xgetbv` raises `#UD` when `CR4.OSXSAVE` is clear. It did not say
who sets `CR4.OSXSAVE`, because nothing in this frontend could: the family named
CR0 and CR3 and stopped. The answer was a C function —
`prepare_bsp_extended_state()` in the aiueos kernel.

Measured 2026-09-02 under QEMU TCG with `-cpu max`: `cpuid` reports AVX and
AVX2, and `CR4.OSXSAVE` is clear, so a pure-Kotoba guard correctly refused the
AVX2 arm on a machine that has AVX2, with no spelling available to fix it.

## Why these arities

None is invented. `kernel-read-cr4` / `kernel-write-cr4` take what
`kernel-read-cr0` / `kernel-write-cr0` take, because a control register is one
machine word read whole and written whole. `kernel-xsetbv` takes what
`kernel-write-msr` takes — index in ECX, value across EDX:EAX — because at the
machine level it is `wrmsr` with a different opcode.

Arity 2 for `xsetbv` rather than 1 is the load-bearing choice. XCR0 is index 0
and it is the only index anyone writes today, so a one-argument spelling looks
reasonable — and it would take the VALUE as the index and write EDX:EAX from
whatever the register happened to hold. The negative row for that case is in the
test.

## There is no `kernel-write-cr2`

CR2 is written by the CPU when a page fault is taken. A kernel that wrote it
would be lying to its own handler about the faulting address. The test asserts
the absence rather than leaving it out, because "we did not add it" and "it must
not be here" read identically in a diff.

## What arity cannot see

Two things, and both are faults rather than wrong answers.

**A sequence.** `xsetbv` requires `CR4.OSXSAVE` already set. The order is
`cpuid` leaf 1 ECX bit 26 (XSAVE) → set CR4 bit 18 → `xsetbv` → `xgetbv`. No
arity check expresses an ordering between separate calls.

**A value.** `xsetbv` raises `#GP` for a bit XCR0 does not define, for bit 0
(x87 state) clear, and for bit 2 (YMM) set without bit 1 (SSE).
`(kernel-xsetbv 0 6)` and `(kernel-xsetbv 0 4)` have the same shape and the
second faults. A literal check would also miss the real call sites, whose value
is `(bit-or (kernel-xgetbv 0) 6)` — see kotoba-kir ADR 0239.

Both are carried in kotoba-native `docs/avx2-guard-sequence.md`.

## Evidence

`kotoba.compiler.kernel-xsetbv-test`, 3 tests / 18 assertions, run on **both**
runtimes: `kbb -M:test -n kotoba.compiler.kernel-xsetbv-test` and
`kbb --backend sci run-tests.cljk` (73 tests / 216 assertions after registration in both lists
of `run-tests.cljk`; being required is not being run).

Positive rows include the sequence the family exists for — read CR4, set bits
9/10/18, write back, then `(kernel-xsetbv 0 (bit-or (kernel-xgetbv 0) 6))` —
analysing as one unit. Negative rows pin the frontend's own literal,
`"kernel privileged operation arity mismatch"`, rather than merely that
something was refused.

Shown to discriminate by deleting `kernel-xsetbv 2` from the map: the three
`xsetbv` negative rows then fail with
`"operation has no admitted lowering"` — the function-call arm's message, which
is exactly the indistinguishable failure the literal pin exists to separate —
and the arity assertion reports `{kernel-read-cr4 0, kernel-write-cr4 1}`.
Restored, 0 failures.
