# ADR 0023: admit the fused dequantize-and-dot family in MC

Status: accepted. Date: 2026-09-02.

## Context

ADR 0009 admitted `:kernel-dot-f32` with the keyset two regions, a ceiling and
a count. kotoba-gmir ADR 0023 adds three operations of the same shape.

## Decision

`:kernel-dequant-dot-q8-0`, `-q4-k` and `-q6-k` carry the same keyset, for the
same reason: the operand SHAPE is the same. `:mir/count` counts blocks rather
than elements, and which it counts is the format's business rather than the
keyset's — MC validates fields, not semantics.

x86-64 only, because `kotoba.mir` refuses them elsewhere.

## Evidence

Suite: 26 tests / 259 assertions. The encoding keyword is derived
(`(keyword (name isa) (name op))`), so no dispatch table needed a row.
