# ADR 0009: The extended control register read

## Status

Accepted.

## Decision

Add `:xgetbv` to `x86-privileged-action-arities` at arity **1**. `xgetbv` reads
XCR[ecx] into edx:eax, so one argument — the XCR index — and one i64 result
carrying both halves.

## Why it is not covered by the `cpuid` four

The `cpuid` actions and this one answer different questions.

`cpuid` says what the **CPU** implements: leaf 1 ECX bit 28 is AVX, leaf 7 EBX
bit 5 is AVX2. XCR0 bits 1 and 2 say what the **operating system** has agreed
to save and restore across a context switch — the SSE state and the upper
halves of the YMM registers. A machine can implement AVX2 while the kernel
running on it has not enabled YMM state saving.

A kernel that reads only `cpuid` and uses YMM anyway does not fault. Its vector
registers are simply not preserved across a context switch, so it computes
wrong answers intermittently and only under load. There is no `cpuid` leaf that
answers this; the only way to ask is `xgetbv`.

## What this table cannot say

`xgetbv` raises `#UD` unless `CR4.OSXSAVE` is set, and the bit that reports
`CR4.OSXSAVE` is `cpuid` leaf 1 **ECX bit 27**. A correct guard tests bit 27
**before** it reads XCR0, or feature detection faults in the middle of itself.

That is a property of a *sequence* of actions, and this table describes one
action at a time. It is not expressible here and is not enforced anywhere;
`kotoba-native` `docs/avx2-guard-sequence.md` carries it as bytes and prose.

## Evidence

`kotoba.gmir-test/xgetbv-takes-the-xcr-index-and-nothing-else`: one argument
validates, zero and two are refused. Shown to discriminate by writing the arity
as 0 — the one-argument program then fails validation with
`GMIR rejected: invalid-x86-privileged` and the zero-argument negative row stops
being negative.

The `cpuid` four are pinned at arity 2 in the same test. They are `(leaf,
subleaf)` and always have been; a `cpuid-subleaf-*` family was proposed on the
belief that they took only a leaf, and this pin is so that belief cannot be
formed from this repository.

Nothing here executes. GMIR owns the arity contract; the encoding
(`0f 01 d0`) lives in `kotoba-native`, where it has been cross-checked against
an assembler and not run — the workstation is an Apple M4 and Rosetta exposes
no AVX.
