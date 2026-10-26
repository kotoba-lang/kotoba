# ADR 0256: the dequantization equations are the oracle

Status: accepted. Date: 2026-09-02.

## Context

kotoba-gmir ADR 0023 declares a fused dequantize-and-dot family, and
kotoba-native ADR 0066 emits two arms for it that are required to agree bit for
bit. "Bit for bit with what" is this file's answer.

## Decision

`kotoba.kir` dequantizes and folds all three formats, and the machine is
required to agree with it.

**The equations are transcribed from `os/aiueos/kernel/qwen35_quant.c`**, which
vendored them from llama.cpp at 3173a564 (MIT), operation for operation and
rounding for rounding. `y = q*d` is one f32 multiply and not a fused anything;
`y = d1*(q&0xF) - m1` is three, in that order, because that is what the C
evaluates; Q6_K's `d * sc[is] * q` associates left, so `d*sc` rounds before it
meets the code.

**The accumulation tree is `dot_scalar`'s** (`qwen35_infer.c:234`): four
accumulators, the lower half of each eight-element group before its upper half,
`(s0+s1)+(s2+s3)`. There is no tail — 32, 256 and 256 are all multiples of
eight. The C has a second tree (`dot_avx2` reduces left to right) and picks at
run time; this family reproduces the scalar one and says so, because "matches
the C" is not checkable while the C has two answers.

**Fuel is charged per ELEMENT**, not per block. A per-block charge would let a
256-element fold run inside the fuel two additions are given.

**The checks are the emitter's, in the emitter's order**, so a program that
traps here traps on the machine: both lengths against the ceiling, both bases
against zero, the block count against the derived limit, then each span
against its own window. The block-count check comes before either span is
formed.

## Evidence

`test/kotoba/kir_kernel_dequant_dot_test.cljk`, 13 tests / 812 assertions.

The dequantization is compared with an INDEPENDENT port of the C — written
with the C's own `y++` / `q += 32` pointer walk rather than this file's
functional form — ELEMENT BY ELEMENT. The fold makes that possible: an
activation vector that is 1.0 at one position and 0.0 everywhere else answers
with exactly that element's dequantized value.

The one thing that probe cannot see is the SIGN of a zero, because
`+0.0 + -0.0` is `+0.0`. Both sides are normalised for it, and an evidence
floor asserts each fixture has non-zero elements to compare — otherwise a
dequantizer that answered zero for everything would satisfy the comparison.

Half precision is a TABLE of twelve hand-derived patterns rather than a second
transcription of `fp16_to_f32`: a copy agrees with its original for the reason
a copy does. The twelve cover zero, negative zero, the smallest and largest
subnormals, the smallest normal and the largest finite half.

No real model bytes. This host carries no GGUF — `mdfind -name .gguf` returned
nothing, a depth-6 `find` over /Volumes and $HOME returned nothing, and no file
above 2 GiB exists under $HOME while the whole volume holds 17 GiB. Every block
is synthesised and the cross-check is against the port of the C.

Break-checked twice, each reddening the test named for it: Q6_K's scale index
as `l/8` rather than `l/16` (189 failures in
`q6-k-dequantizes-what-the-c-dequantizes`); Q8_0's codes read unsigned (135
failures across `q8-0-codes-are-signed` and
`q8-0-dequantizes-what-the-c-dequantizes`).
