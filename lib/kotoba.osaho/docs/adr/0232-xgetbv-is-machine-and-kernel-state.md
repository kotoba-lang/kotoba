# ADR 0232: `kernel-xgetbv` is machine AND kernel state, so the oracle refuses it

## Status

Accepted.

## Context

An AVX2 guard cannot be written with `cpuid` alone. `cpuid` leaf 1 ECX bit 28
says the CPU implements AVX; XCR0 bits 1 and 2 say the *operating system* has
agreed to save and restore the SSE and YMM register state across a context
switch. A kernel that reads only the first and uses YMM anyway computes wrong
answers intermittently and only under load, because its vector registers are
not preserved. Reading XCR0 is `xgetbv`, and this repository had no operator
for it — so the guard could not be written in Kotoba at all, and the aiueos
K16 image reaches it through inline asm in `qwen35_infer.c`.

## Decision

Add `kernel-xgetbv`, arity 1, to both sets that govern privileged operations:

- **`eval-expr`'s refusal set.** The interpreter traps
  `:kernel-privileged-unavailable` rather than answering.
- **`lower`'s `kernel-operations`.** Membership marks a module kernel-native,
  which suppresses the constant oracle.

`xgetbv` reads XCR[ecx] into edx:eax; the operator takes the XCR index and
returns the two halves as one i64.

## Why both sets, and why the second is the easy one to miss

They fail differently and neither substitutes for the other.

The refusal set stops the interpreter inventing a value. That much is the same
argument the `cpuid` four already make, and `xgetbv` makes it **twice over**: a
`cpuid` result is a property of the machine, and XCR0 is a property of the
machine *and* of the kernel running on it *at the moment of the read*. It
changes when the kernel enables the YMM state bit. There is no answer that is
right even in principle, and the value the caller branches on is "may I use
AVX2".

`kernel-operations` is the one that is easy to forget, because forgetting it
does not produce a wrong answer — it produces a **failure to compile a valid
program**. The single real argument to `kernel-xgetbv` is the literal `0`. A
constant folder sees an operation over one constant with nothing about it
suggesting an effect, tries to evaluate it, and hits the trap the first set
installed. The compile aborts. The `cpuid` four are in this set for the same
reason (their operands are literals at every call site); `xgetbv` is slightly
worse because it has only one operand and it is always zero.

## Evidence

`kotoba.kir-kernel-privileged-test`, 2 tests / 19 assertions. Shown to
discriminate by removing the symbol from each set in turn:

| removed from | result |
| --- | --- |
| `lower`'s `kernel-operations` | `xgetbv-marks-a-module-kernel-native` **errors**, with `{:trap :kernel-privileged-unavailable, :operation kernel-xgetbv}` thrown out of `lower` itself |
| `eval-expr`'s refusal set | the refusal row **fails**, with `:unknown-function` where `:kernel-privileged-unavailable` is pinned |

The `lower` test carries a control — `(bit-or 6 1)` must still fold to 7 — so a
`lower` that had stopped folding everything cannot pass it.

## Not done, and deliberately

**No `kernel-cpuid-subleaf-*` family.** It was proposed on the assumption that
the existing `cpuid` operators take only a leaf. They do not: all four are
**arity 2, `(leaf, subleaf)`**, in this repository's refusal set, in
`kotoba-sema`'s `kernel-privileged-operations`, in `kotoba-gmir`'s
`x86-privileged-action-arities`, and in `kotoba-native`'s `emit-kernel-cpuid`,
whose own comment explains that a leaf whose subleaf was whatever happened to
be in ECX is a different query. Leaf 7 subleaf 0 is spelled
`(kernel-cpuid-ebx 7 0)` today. A second family would be a duplicate.

**No execution evidence.** This repository is the oracle; it asserts that the
operation is refused, never that any byte runs. The encoding lives in
`kotoba-native` and has been cross-checked against an assembler, not executed:
the workstation is an Apple M4 and Rosetta exposes no AVX.
