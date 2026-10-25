# ADR 0041: `xgetbv` is `rdmsr` with one less hazard

- Status: accepted
- Date: 2026-09-02

## Decision

Emit `kernel-xgetbv` on x86-64, as `0f 01 d0`, on both lowering paths: the
machine-IR pilot (`kir-x86-privileged-ops` → `:xgetbv` → `x86-privileged`) and
the direct emitter (`emit-kernel-xgetbv` in `x86_64.cljc`). Reject it on
AArch64, pinned by `isa_parity_test`'s `x86-only` list.

Upstream: kotoba-kir ADR 0229 (interpreter refusal and oracle marker),
kotoba-sema ADR 0003 (arity 1 in `kernel-privileged-operations`), kotoba-gmir
ADR 0009 (`:xgetbv 1` in `x86-privileged-action-arities`).

## Why this operator and not another `cpuid` leaf

`cpuid` says what the **CPU** implements. XCR0 says what the **operating
system** has agreed to save and restore across a context switch — bit 1 the
SSE state, bit 2 the upper halves of the YMM registers. A machine can implement
AVX2 while the kernel running on it has not enabled YMM state saving, and a
kernel that reads only `cpuid` and uses YMM anyway **does not fault**: its
vector registers are simply not preserved, so it computes wrong answers
intermittently and only under load. There is no `cpuid` leaf that answers this.

## The encoding, and what it does not need

`xgetbv` reads XCR[ecx] into EDX:EAX. Structurally that is `rdmsr` with a
different opcode, so both arms are `emit-kernel-read-msr` / the `:read-msr`
case with `0f 32` replaced by `0f 01 d0`:

```
  mov rcx, rax     ; index -> ecx
  xgetbv           ; -> edx:eax
  shl rdx, 32
  or  rax, rdx
```

Its closer *relative* is `cpuid` — both answer "what can this machine do" — but
it does not share `cpuid`'s hazard. **`cpuid` writes EBX unconditionally**,
which is why `emit-kernel-cpuid` carries `push rbx` / `pop rbx`: RBX is
callee-saved in SysV and nothing else in this backend touches it, so the
prologue never saves it, and a `cpuid` that returned to the loader with RBX
destroyed would corrupt a frame at an arbitrary distance from the instruction.
**`xgetbv` writes EAX and EDX only.** The save is not needed and is not
emitted, and the test asserts its *absence* rather than merely omitting it —
"we did not add it" and "it must not be there" read identically in a diff.

No mask on either half, for the reason `emit-kernel-read-msr` already gives:
the instruction writes the 32-bit EAX and EDX, and a 32-bit write zeroes the
upper half of its containing 64-bit register, so both halves arrive already
isolated.

## What no emitter can enforce

`xgetbv` raises `#UD` unless `CR4.OSXSAVE` is set, and the bit that reports
`CR4.OSXSAVE` is `cpuid` leaf 1 **ECX bit 27**. A guard must test bit 27
**before** reaching this instruction, or feature detection faults in the middle
of itself. That is an ordering constraint between two separate operators;
nothing here can express it. `docs/avx2-guard-sequence.md` carries it as bytes
and prose, and is the only place it exists.

## Measured honestly: the direct arm was not reached through `emit-program`

`emit-program` sends a word-result function whose body pilots through
`machine-ir/compile-expression`, and everything else reaches `x86_64.cljc`'s
own `emit-kernel-*`. **No `emit-program` input was found that takes the second
branch for this operator.** Every shape tried piloted: plain, `let`-bound,
inside `if`, as a nested argument, mixed with a string call, split across two
functions, and with `:vector-i64` and `:string` declared results. The same
appears to be true of `emit-kernel-cpuid` beside it, which is not a claim this
ADR investigated further.

The direct arm is kept for parity with its siblings — leaving `xgetbv` the one
privileged operator without one would make it the one that breaks if the pilot
ever declines — and it is tested by direct invocation rather than through
`emit-program`, because that is what can honestly be shown.

## Evidence

`kotoba.native.isa-parity-test/xgetbv-emits-the-published-opcode-on-both-lowering-paths`.
Both byte sequences were disassembled with
`llvm-mc --triple=x86_64-unknown-linux-gnu --disassemble --output-asm-variant=1`
(LLVM 22.1.7) and read back as `xgetbv` surrounded by the named moves.

Shown to discriminate three ways:

| break | result |
| --- | --- |
| pilot arm's opcode typed as `rdmsr`'s (`0f 32`) | both pilot rows red |
| `push rbx` copied from the `cpuid` arm into the `xgetbv` arm | the RBX row red |
| direct arm shifts RAX instead of RDX | the direct golden red |

**Not executed.** This workstation is an Apple M4 and Rosetta exposes no AVX.
Execution belongs to QEMU TCG `-cpu max` or to K16.

## Also not done

**No `kernel-cpuid-subleaf-*` family.** It was proposed on the assumption that
the existing `cpuid` operators take only a leaf. They do not: all four are
arity 2, `(leaf, subleaf)`, in `kir-x86-privileged-ops`, in
`emit-kernel-cpuid`'s own signature, in `x86-privileged-action-arities` and in
`kernel-privileged-operations`. Leaf 7 subleaf 0 is spelled
`(kernel-cpuid-ebx 7 0)` today.

## Renumbering note

Landed as `0039` and moved to `0041`: two streams working concurrently each
numbered a new ADR `0039` on 2026-09-02 (`-uefi-firmware-boundary-encodings`
and this one). This one moved because it can be; a numbered ADR whose number
is shared is not a reference. Same day, the same thing happened three times
over at `0229` in kotoba-kir, where two of the three still share the number.
