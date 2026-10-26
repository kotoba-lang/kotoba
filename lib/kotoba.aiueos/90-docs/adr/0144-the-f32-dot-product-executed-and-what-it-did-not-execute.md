# ADR 0144 — The f32 dot product, executed, and what it did not execute

Status: accepted (2026-09-02)

## Context

`kernel-dot-f32` (kotoba-gmir ADR 0010, kotoba-native ADR 0043) is one MC
instruction that selects **one of two instruction sequences at run time**: an
AVX2 sequence where a `cpuid`/`xgetbv` guard says the machine has it, and a
legacy scalar SSE sequence where it does not. Its central claim is that the two
compute a bit-identical answer.

Six compiler repositories can assert the bytes of both sequences. None of them
can assert that claim, because it is a claim about a machine. This workstation
is an Apple M4 and Rosetta exposes no AVX, so the only machine available that
can answer at all is QEMU TCG.

## What is here

`os/aiueos/native/dot-f32-probe.kotoba` — a **test variant** of the pure-Kotoba
kernel, not a second production kernel. `kernel.kotoba` is untouched. The probe
boots the same way, finds one conventional page from the UEFI memory map, fills
two f32 regions with known bit patterns, folds them with `kernel-dot-f32`, and
writes the answer to the 0xe9 debug console as eight hex digits.

`os/aiueos/scripts/smoke-qemu-dot-f32.cljk` — nbb, mirroring the `.sh` smoke
scripts' QEMU invocation, run twice: `-cpu max` and `-cpu qemu64`.

## The vector names the tree

A = `[2^24, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]`, B = twelve `1.0`s. Twelve, so one
eight-element block runs and a four-element tail follows it. 2^24 is the largest
integer after which binary32 spacing becomes 2, so each 1 added to it *alone*
rounds away and each *pair* of 1s does not.

- `0x4B800004` — four lanes, lower half before upper, `(s0+s1)+(s2+s3)`, tail
- `0x4B800000` — a straight left-to-right sum: every 1 lost into the gap

So the digits do not merely say "a dot product happened". They say which one.

## Observed

```
  max:    features=6 ["avx" "avx2"]  arm=scalar  digits=4B800004
  qemu64: features=0 []              arm=scalar  digits=4B800004
```

Both exited 33. `kotoba.kir`'s reference interpreter answers `0x4B800004` for
the same input.

## What that establishes, and what it does not

**Executed and correct:** the scalar arm, on two different CPU models,
answering exactly what the oracle answers — which covers the accumulation tree,
the bounds checks, the guard's own `cpuid`/`xgetbv` sequence (it ran, and
correctly answered *no*), the operand rescue across `cpuid`, the sign
extension, and the whole compiler chain end to end on a real machine.

**Not executed: the AVX2 arm.** The control says why, and it is the guard
working exactly as designed. `-cpu max` reports AVX and AVX2 in `cpuid`, and
**CR4.OSXSAVE is clear**, because nothing set it. A kernel that used YMM anyway
would not fault; it would compute wrong answers intermittently and only under
load, because its vector registers are not preserved. That is precisely what
leaf 1 ECX bit 27 is tested for.

The probe reports the guard's four inputs as a hex nibble for exactly this
reason. Without it, "both models printed the same digits" would have been an
agreement between one sequence and itself, read as a proof about two.

The script exits **2** — not 0 and not 1 — when the AVX2 arm was not exercised.

## The gap this measured

Setting CR4.OSXSAVE and then XCR0 needs a CR4 write and `xsetbv`, and **neither
has a Kotoba spelling**. Measured 2026-09-02 across kotoba-sema, kotoba-gmir and
kotoba-native: `kernel-write-cr0` exists, there is no CR4 operator, and there is
no `kernel-xsetbv` anywhere in the surface.

`prepare_bsp_extended_state()` in `os/aiueos/kernel/qwen35_infer.c` is the C
kernel doing it — CR4 bits 9, 10 and 18, then `xsetbv`. A pure-Kotoba kernel
cannot, so a pure-Kotoba kernel cannot use YMM at all today. That is a K16 gap
of its own, and it is larger than this operation: every future AVX2 kernel
(fused dequantisation first) runs into it before its first vector instruction.

## Two gates that were shut

Compiling this probe found two operations admitted everywhere except
`kotoba-verifier`, which admits by membership:

- `kernel-dot-f32` — expected; opened in kotoba-verifier ADR 0023.
- **`kernel-xgetbv`** — not expected. Landed in kotoba-gmir, kotoba-kir,
  kotoba-sema and kotoba-native with an ADR each, and never there.

And one in kotoba-native: `dce-gmir` deleted two of the operation's literal
operands, because their key names were missing from a hand-written source-key
list (kotoba-native ADR 0044).

All three were found by compiling a program. None could have been found by the
compiler suites, which were green.
