# ADR 0088: a PTQ1_0 row is folded where it lies

Status: accepted. Date: 2026-09-26.

## Context

kotoba-gmir ADR 0031 declares `kernel-dequant-dot-ptq1-0`, and osaho ADR
0272 gives it an oracle. PTQ1_0 is 402 of the Ternary Bonsai 2 27B
artifact's 851 tensors (aiueos ADR-0222), and until now AIUEOS's live matvec
wrote every such row out as f32 and then dotted it.

A 28-byte block is `qs[24]` (five base-3 digits per byte), `qh[2]` (four per
byte), then `d` as fp16. Element e reads `qs[e mod 16]` at digit `e/16`
below 80, `qs[16 + (e-80) mod 8]` at digit `(e-80)/8` below 120, and
`qh[(e-120) mod 2]` at digit `(e-120)/2` after. Digit n is
`((byte * 3^n) & 255) * 3 >> 8`, and the weight is `(digit - 1) * d`.

## Decision

x86-64 emits both arms; AArch64 refuses, by the same
`:x86-simd-target-mismatch` Q4_K gets.

**Fifteen of the sixteen eight-element groups are one load at one digit**
(`x86-dequant-ptq1-0-groups`, derived from `ptq1-0-element`, not written
out): `vpmovzxbd` widens eight consecutive bytes, and `t <- 3t mod 256` is
applied `digit` times before the final `3t >> 8`. `3t` is `4t - t`
(`vpslld` then `vpsubd`), so no integer-multiply form is needed. The
sixteenth group reads `qh[0]` and `qh[1]` alternately at digits
0,0,1,1,2,2,3,3, which no load can gather: its eight digits are computed in
RAX, packed as bytes into RDX, and moved across with one new form,
`:vmovq-from-gpr` (VEX.128.66.0F.W1 6E).

The legacy arm computes each element in RAX with `imul`/`and`/`shr` and
folds it into accumulator `e mod 4`. Both arms then run the family's
unchanged tree: `(digit-1)` converted, times `d`, times `x`, lower half of
each group before its upper half, `(s0+s1)+(s2+s3)`.

## Verification

- `kotoba.native.dequant-ptq1-test`: the element geometry equals a
  transcription of the C's three stage loops, element by element, and a
  perturbed recipe (qh at digit `q mod 4`) disagrees. The byte runs pinned
  there were read back from this emitter's output with Apple LLVM
  `objdump -d`: 45 `3t` steps (30 of them followed by the `255` mask), 15
  `>> 8` closes, one `vmovq`+`vpmovzxbd` gather, 128 `cvtsi2ss`.
  Replacing the qh digit `(e-120)/2` with `(e-120) mod 4` in
  `ptq1-0-element` turns the geometry assertions red and nothing else.
- Execution of both arms: aiueos `smoke-qemu-dequant-ptq1.cljk`, under
  `-cpu max` (AVX2) and `-cpu qemu64` (scalar), against the oracle's
  `C88A9DFA`.

## Consequences

The ceiling is the family's: 128 blocks, 16,384 elements. A 17,408-column
row is still two calls and therefore a different tree, so a caller that must
match the materialising path keeps it for rows that wide.
