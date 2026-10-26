# ADR 0185: a fixture of equal weights cannot see the geometry

Status: accepted. Date: 2026-09-03.

## Context

kotoba-native ADR 0074 unrolled `kernel-dequant-dot-q4-k` and
`kernel-dequant-dot-q6-k` — the two K-quant formats ADR 0066 declared and
refused by name, because a K-quant block's dequantization parameters change
part-way through it and its thirty-two eight-element groups are therefore not
a loop. Two arms per format, AVX2 and legacy SSE, required to agree bit for
bit. The compiler's suites can assert their bytes; they cannot assert that the
two arms compute the same number, because that is a claim about a machine.

ADR 0165 established the shape of the evidence and, more usefully, recorded
what a weak fixture costs: `[2^24, 1, 1, …]` separates the contract's tree from
a straight left-to-right sum and does NOT separate it from its own
upper-half-first twin, because with a zero accumulator and equal elements
`(0+a)+b` and `(0+b)+a` are the same number. A deliberately broken emitter
printed the expected digits under both CPU models.

This ADR adds the probe and the smoke for the K-quants, and records TWO ways a
fixture can be too weak — the second of which does not arise for Q8_0 at all.

## A K-quant fixture has to discriminate two different things

**The tree.** Same problem ADR 0165 solved, with a new twist. Copying that
ADR's `[2^24, 2, 3, 4, 5, 6, 7, 8]` does not work here: Q8_0's block is four
groups and a K-quant's is thirty-two, so the accumulator grows eight times
further, and by the end the small lanes are absorbed whichever order they
arrive in. Measured 2026-09-03 against `kotoba.kir` over a grid of block
counts and leading values, the contract and its upper-half-first twin printed
the SAME digits for Q4_K at 2^24 and for Q6_K at 2^24, 2^20, 2^19 and 2^16.
The values that separate all three orders are **2^22 for Q4_K** and **2^18 for
Q6_K**, and they are different numbers for the same reason the two formats'
answers are: what has to be true is a relationship between the accumulator's
final magnitude and the size of the terms being folded into it, and the
formats' weights differ.

**The geometry.** This is new. Q8_0's code is a whole signed byte, so there is
nothing to get wrong about WHERE it comes from beyond the byte offset. A
K-quant code is assembled from fields: which byte, which nibble half of it,
which of eight (scale, min) pairs or sixteen signed scales, and for Q6_K which
two-bit field of a fifth byte. **A fixture whose weights are all 1.0 says
nothing about any of that, because every wrong answer is also 1.0.**

So no weight in this probe equals any other. The codes are the byte index
itself — `qs[t] = t`, `ql[t] = t`, `qh[t] = t` — so a wrong byte or a wrong
nibble half is a different number rather than the same one; the Q4_K scale
bytes are `[1 2 3 4] [0 0 0 0] [5 6 7 8]`, which `get_scale_min_k4` reads as
the eight pairs `(1,0) … (8,0)`; the Q6_K scales are 1..16. The two blocks
differ in `d` (1.0 and 2.0) so that a wrong per-block pointer advance reads a
different scale rather than an identical one.

The eight answers this separates, all measured against `kotoba.kir`:

| | contract | upper half first | left to right | nibble halves swapped | neighbouring scale |
|---|---|---|---|---|---|
| Q4_K | `4FE700BC` | `4FE700BD` | `4FE700B8` | `4FEA00CF` | `4FC600BD` |
| Q6_K | `CF4602C5` | `CF4602C3` | `CF4602C0` | `CF448238` | `CF3BE1C6` |

The smoke names the near-miss when it sees one, rather than reporting "the
digits differ": a wrong answer that is one of these eight says which mistake
was made.

## Decision

`os/aiueos/native/dequant-kquant-probe.kotoba` and
`os/aiueos/scripts/smoke-qemu-dequant-kquant.cljk`, siblings of the Q8_0 pair
and following ADR 0155's three outcomes (a disagreement is exit 1, an
unanswerable question is exit 3, a stale artifact is exit 4) and its freshness
receipt before every boot.

Two activation vectors rather than one, because the two formats need different
leading values. Rewriting one vector between the folds would make the second
fold's answer depend on the first having finished, which is a property of the
program and not of the instruction under test.

## Evidence

```
-cpu max:    exit=33 console="1F4FE700BCCF4602C5KQ"
-cpu qemu64: exit=33 console="004FE700BCCF4602C5KQ"
  max:    enable=1 features=15 ["osxsave" "avx" "avx2" "xcr0-ymm"] arm=avx2
          q4-k=4FE700BC q6-k=CF4602C5
  qemu64: enable=0 features=0 [] arm=scalar
          q4-k=4FE700BC q6-k=CF4602C5
AIUEOS_DEQUANT_KQUANT_QEMU_OK both-arms-executed and-agree-with-kotoba-kir exit=33
```

**And two broken emitters, at the machine level, because a green nobody has
seen go red is not evidence.** The compiler's suite catches these too; that is
a different claim, since a test can agree with an emitter that is wrong in the
same way the test is.

1. The two `vaddps` of the K-quant vector group swapped — `-cpu max` printed
   `4FE700BD` while `-cpu qemu64` printed `4FE700BC`, and the smoke reported
   *"that is Q4_K with the upper half of each group added first"*. This is
   exactly the defect ADR 0165's first fixture could not see.
2. The Q4_K nibble half inverted — BOTH models printed `4FEA00CF`, and the
   smoke reported *"that is Q4_K with the nibble halves swapped"*. A tree
   fixture alone would not have caught this: the summation order was correct
   throughout.

Each control was reverted and the clean run re-observed green afterwards.

## Consequences

- Two of the model's four dominant K-quant paths now have machine code with an
  executed proof. Q4_K and Q6_K are 184 of the Qwen3.5 model's 866 tensors.
- **Nothing in `qwen35_infer.c` calls any of these instructions.** `matvec_range`
  still runs the C for every token, and this probe is a test variant of the
  pure-Kotoba kernel, not a change to the K16 image. The K16 image is unchanged
  by this ADR.
- **The smoke is not yet reproducible from landed code.** It needs an `amu`
  whose `deps.edn` pins kotoba-native at or after
  `1072816` and kotoba-kir/kotoba-sema at or after the DEQUANT-FUSION
  landings; amu main pins kotoba-kir `08bdab8b` and kotoba-sema `f932c61a`,
  which predate the family and reject `kernel-dequant-dot-q4-k` at the subset
  check with `operation has no admitted lowering`. Until that pin moves, this
  harness reports COULD-NOT-RUN compile-failed against amu main. Measured
  2026-09-03, and it is the same gap ADR 0155 found for
  `AIUEOS_DOT_F32_QEMU_OK`.
- The compile fuel is `1048576`, which is `max-native-fuel`. A larger budget is
  rejected by name (`native fuel budget is not admitted`), so this probe cannot
  grow much: it currently folds 2 blocks of each format, 512 elements each.
- The IQ family (IQ3_XXS, IQ3_S, IQ4_XS, IQ2_S — 306 of 866 tensors and the
  dominant types) is not addressed here and needs a codebook grid reachable
  from a kernel object before it can be declared at all.
