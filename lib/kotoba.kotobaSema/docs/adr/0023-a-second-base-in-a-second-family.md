# ADR 0023: a second base, in a second family

Status: accepted. Date: 2026-09-02.

## Context

ADR 0006 added `kernel-base-positions` because `kernel-dot-f32` was the first
kernel memory operation whose base was not argument 0 — and the provenance walk
was the literal `(first args)`, so its second base would have flowed past
`traceable-base?` entirely.

The fused dequantize-and-dot family (kotoba-gmir ADR 0023) has the same shape,
three times.

## Decision

`kernel-dequant-dot-q8-0`, `-q4-k` and `-q6-k` enter
`kernel-memory-operations` at arity five and `kernel-base-positions` at
`[0 2]`. Nothing else changes: the mechanism ADR 0006 built is the mechanism.

Per-format rows rather than one row for a family, because the table is
per-format data and the failure mode of a missing row is quiet. A head absent
from `kernel-memory-operations` falls through to "unknown function" — a
different sentence — and a head absent from `kernel-base-positions` gets the
default `[0]`, which compiles and leaves a pointer in position 2 that nothing
looked at.

## Evidence

`test/kotoba/compiler/kernel_dequant_dot_test.cljk`, 6 tests / 43 assertions,
every one of them per format: arity in both directions, reserved name, the
`:i64` result, `[0 2]`, both parameters tainted, a computed base refused in
either position, and a `kernel-subregion` narrowing admitted in either position
as the control. `SCANNED formats` asserts the count is three.

Suite: 200 tests / 968 assertions.
