# ADR 0272: a ternary digit needs no table

Status: accepted. Date: 2026-09-26.

## Context

kotoba-gmir ADR 0031 declares `kernel-dequant-dot-ptq1-0`: Prism's
group-128 ternary, 28 bytes per 128 elements, 402 of the Ternary Bonsai 2
27B artifact's 851 tensors. The machine is required to agree with this
oracle bit for bit, so the oracle comes first.

## Decision

`dequantize-block` gains a PTQ1_0 arm transcribed from
`dequantize_row_ptq1_0` (PrismML-Eng/llama.cpp @9a9394a8,
`ggml/src/ggml-quants.c:2255`): element e reads `qs[e mod 16]` with digit
`e / 16` below 80, `qs[16 + (e-80) mod 8]` with digit `(e-80) / 8` below
120, and `qh[(e-120) mod 2]` with digit `(e-120) / 2` after. Digit n of a
byte is `((byte * 3^n) & 255) * 3 >> 8`; the weight is `(digit - 1) * d`,
one exact multiply. The accumulation tree is the family's, unchanged.

## Verification

`kotoba.kir-dequant-ptq1-test` compares every element of three blocks (three
scales, one negative) through one-hot folds against a transcription written
with the C's own loop nest -- `SCANNED 128 DISAGREEMENTS 0` for each -- and a
three-block row against `dot_scalar`'s tree on activations where left-to-right
gives a different answer (asserted). Reproduce:

    kbb -M:test -n kotoba.kir-dequant-ptq1-test

Replacing the qh stage's digit `(e-120) / 2` with `(e-120) mod 4` turns it
red at elements 121..126 and in the whole-row fold, and nowhere else.
