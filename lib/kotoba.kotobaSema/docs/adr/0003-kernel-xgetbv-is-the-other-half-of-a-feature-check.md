# ADR 0003: `kernel-xgetbv` is the other half of a CPU feature check

## Status

Accepted.

## Context

`kernel-privileged-operations` has carried the `cpuid` four since they were
added, and they cannot express an AVX2 guard on their own.

`cpuid` leaf 1 ECX bit 28 says the **CPU** implements AVX. XCR0 bits 1 and 2
say the **operating system** has agreed to save and restore the SSE and YMM
register state across a context switch. Those are different questions with
different answers, and a kernel that asks only the first and uses YMM anyway
does not fault — it computes wrong answers intermittently and only under load,
because its vector registers are not preserved across a context switch.

Reading XCR0 is `xgetbv`, and there was no operator for it. aiueos asks both
questions today, in inline asm (`kernel/qwen35_infer.c`), for want of one.

## Decision

Admit `kernel-xgetbv` at **arity 1**: `(kernel-xgetbv index)` yields the
extended control register at that index, its EDX:EAX halves joined into one
i64. One argument, because `xgetbv` reads exactly one input, the XCR index in
ECX.

It goes in `kernel-privileged-operations` and is therefore never oracled, for a
reason one step stronger than the `cpuid` four's. A `cpuid` result is a
property of the *machine*. XCR0 is a property of the machine **and** of the
kernel running on it **at the moment of the read** — it changes when that
kernel enables the YMM state bit, so the same expression yields different
values five instructions apart.

## The constraint an arity map cannot carry

`xgetbv` raises `#UD` when `CR4.OSXSAVE` is clear, and the bit that reports
`CR4.OSXSAVE` is `cpuid` leaf 1 **ECX bit 27**. A guard must test bit 27
**before** it reads XCR0, or feature detection faults in the middle of itself.

That is an ordering constraint between two separate calls. Nothing in this
frontend can express it — arity is the whole of what a privileged operation is
checked for. It is written in the operator's comment, in the test namespace,
and in `kotoba-native`'s `docs/avx2-guard-sequence.md`, and it is enforced
nowhere. Any admission mechanism that could enforce it would be a larger
change than this one.

## Why arity is worth pinning from both sides

`kernel-privileged-operations` is a symbol-to-count map, and `validate-expr`'s
privileged arm checks the count and then walks the arguments. That number is
the only thing between a malformed call and a backend — and it is stated
independently in three repositories (here, `kotoba-gmir`'s
`x86-privileged-action-arities`, `kotoba-native`'s emitter) with nothing
keeping them equal but review.

`kotoba.compiler.kernel-xgetbv-test` pins it from both directions, with the
frontend's own reason literal rather than the fact of rejection: an operation
that is *absent* from the map is also rejected, as `"operation has no admitted
lowering"`, and looks identical from outside. Measured:

| break | result |
| --- | --- |
| entry removed | the arity rows report `"operation has no admitted lowering"` where `"kernel privileged operation arity mismatch"` is pinned |
| entry written as arity 2 | arity 1 stops analyzing and arity 2 starts — caught in both directions |

## Not done

**No `kernel-cpuid-subleaf-*` family.** It was proposed on the belief that the
existing `cpuid` operators take only a leaf. They do not: all four are arity 2,
`(leaf, subleaf)`, and this file's own comment already explains why. Leaf 7
subleaf 0 is spelled `(kernel-cpuid-ebx 7 0)`. The test pins all four arities
so the belief cannot be formed again from this repository.
