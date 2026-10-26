# ADR 0165: two arms that agree on the wrong fixture agree about nothing

Status: accepted. Date: 2026-09-02.

## Context

kotoba-native ADR 0066 landed `kernel-dequant-dot-q8-0`: one opaque MC
instruction that widens a packed Q8_0 weight row inside the register file and
folds it against f32 activations, with an AVX2 arm and a legacy-SSE arm
required to agree bit for bit. ADR 0138 established the shape of the evidence
for that kind of claim — the same artifact under `-cpu max` and `-cpu qemu64`,
whose feature nibbles prove the two runs saw different machines.

This adds the probe and the smoke for the fused family, and records a defect in
the first version of both.

## The fixture is the whole experiment, and the first one was too weak

`dot-f32-probe.kotoba` folds `[2^24, 1, 1, ... 1]` against ones, and its
answer `0x4B800004` separates the contract's tree from a straight
left-to-right sum. The first version of this probe copied that idea.

It does not separate the contract from its own nearest twin. The contract adds
the LOWER half of each eight-element group into its four lanes before the
upper half. With every element equal and the accumulator starting at zero,
`(0+a)+b` and `(0+b)+a` are the same number — so an emitter with its two
`vaddps` swapped compiles, boots, and prints the expected digits.

Measured: that emitter was built, and both models printed `4B80000C`, and the
smoke exited 0.

## Decision

The activations repeat `[2^24, 2, 3, 4, 5, 6, 7, 8]`. Above 2^24 the binary32
spacing is 2, so what survives an addition depends on what the accumulator
already holds, and the three plausible orders of summation give three different
answers for one block:

| tree | answer |
|---|---|
| four lanes, lower half before upper, `(s0+s1)+(s2+s3)` — the contract | `0x4C800012` |
| the same four lanes, upper half first | `0x4C800011` |
| a straight left-to-right sum | `0x4C800010` |

Re-measured with the same broken emitter: `-cpu max` printed `4C800011` while
`-cpu qemu64` printed `4C800012`, the two arms disagreed on one machine, and
the smoke exited 1 naming the disagreement with the oracle.

The weights are 128 Q8_0 blocks whose every code is 1 and whose every scale is
a binary16 1.0, so each product IS its activation and the answer is a statement
about summation order and nothing else.

## Two timed folds, and what the number is not

`kernel-rdtsc` brackets a 256-element fold and a 4096-element one, after a
THROWAWAY fold that is not timed. The throwaway is not hygiene: measured
without it, the 256-element fold reported 788,000 ticks and the 4096-element
one 279,000, because the first call through a sequence pays for QEMU to
TRANSLATE it and that cost is larger than the whole loop. A difference taken
across a cold call measures the translator.

The smoke reports `(large - small) / 3840` per arm. What that number is NOT is
a cycle count: `rdtsc` under TCG without `icount` reads a virtual clock derived
from HOST time, so it measures how long QEMU takes to translate and run the
guest. Per-instruction translation cost dominates there and a 256-bit vector
operation costs QEMU about what a scalar one costs, so the ratio
systematically understates what the same two arms would do on a machine with
AVX2. Four runs on 2026-09-02 under changing load gave ratios of 1.17, 1.45,
1.55 and 1.57 — the spread is the load, not the code.

The defensible statement about speed is a COUNT, and it lives in kotoba-native
ADR 0066: eight elements cost 13 guest instructions vectorised and 53 scalar.
This workstation is an Apple M4 whose Rosetta exposes no AVX, so there is no
silicon here that can turn that count into a time.

## Evidence

    -cpu max:    exit=33 console="1F4C800012000059D80003A980DQ"
    -cpu qemu64: exit=33 console="004C800012000071480005A168DQ"
      max:    enable=1 features=15 [osxsave avx avx2 xcr0-ymm] arm=avx2 digits=4C800012
      qemu64: enable=0 features=0  []                          arm=scalar digits=4C800012
    AIUEOS_DEQUANT_DOT_QEMU digits=4C800012 arms-exercised=avx2,scalar
    AIUEOS_DEQUANT_DOT_Q8_0_TCG_TICKS_PER_ELEMENT scalar=88.54 avx2=56.51 ratio=1.57
    AIUEOS_DEQUANT_DOT_QEMU_OK both-arms-executed and-agree-with-kotoba-kir exit=33

`4C800012` is what `kotoba.kir` answers for the same bytes.

## What this does not say

The K16 image is unchanged. Nothing in `qwen35_infer.c` calls this instruction,
`matvec_range` still runs the C, and no model tensor has been folded by it. The
probe is a test variant of the pure-Kotoba kernel, not a second production
kernel, and it links no C object — the same no-foreign-artifact floor
`smoke-qemu-dot-f32.cljs` keeps.

Q4_K and Q6_K are declared and have oracles and are refused by the backend by
name. The IQ family — 306 of the model's 866 tensors, and its dominant types —
is not declared at all; kotoba-native ADR 0066 records that the literal pool
landed by the boot-compiler stream makes their codebook grids expressible from
a kernel object, which is what had blocked them.
