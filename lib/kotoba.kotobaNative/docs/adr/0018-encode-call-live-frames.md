# ADR 0018: Encode call-live frames

## Status

Accepted.

## Context

MIR now distinguishes liveness-minimal straight-line call frames from its
conservative all-vreg fallback. Both contain calls and therefore require the
same target ABI stack and return-address treatment even when the optimized
frame owns zero spill slots.

## Decision

Consume merged MIR `36a49266cde0a3d38dfd5eb8626af5919f753a22`
and MC `d56b6bcdce919f55084b071036af80e6b420db70`.

Treat both `:call-live` and `:all-vregs` as call-bearing frame policies. On
x86-64, preserve the call-site stack alignment adjustment. On AArch64, save
and restore FP/LR. Spill slots continue to use the existing bounded eight-byte
layout, including the valid zero-slot call-live case.

## Consequences

The representative scalar caller reaches both production encoders with one
slot, one save, and one lazy reload instead of four slots and an all-definition
store/load stream. For that pinned KIR module, emitted code decreases from 123
to 84 bytes on x86-64 and from 108 to 88 bytes on AArch64. The conservative
policy remains byte-compatible and is still selected for CFG, phi, or excess
register pressure.

This ADR does not claim CFG liveness, slot coloring, indirect calls, aggregate
call boundaries, or Rust-wide performance parity.
