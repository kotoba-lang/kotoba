# ADR 0007: Assign function-entry arguments in parallel

## Status

Accepted. The five-live-argument fallback below is superseded by ADR 0008;
the marker and parallel-copy decisions remain current.

## Context

MIR v3 already assigns outgoing call arguments in parallel, but function entry
previously treated each incoming argument as an ordinary sequential
definition. On x86-64, the ABI input order (`rdi`, `rsi`, `rdx`, `rcx`, `r8`)
overlaps the allocator profile (`rax`, `rcx`, `rdx`, `r8`). Sequential moves can
overwrite a later input before it is consumed, while the conservative spill
path avoids the hazard at the cost of storing every argument and value.

## Decision

Every physical MIR v3 function begins with exactly one canonical argument
marker per declared parameter. Marker destinations are the target ABI input
registers in index order and are validated independently of allocator policy.

For a register-allocated function, MIR assigns used parameters to allocator
registers as one parallel-copy group. The existing cycle-safe scheduler orders
overlapping copies and reserves one temporary frame slot only when a cycle
requires it. Unused parameters retain their ABI markers but consume no
allocator register. A destination may reuse its left operand's register when
that operand dies at the instruction.

Four simultaneously used scalar parameters therefore remain register-only on
both supported targets. Five simultaneously used parameters exceed the
four-register allocator profile and retain the deterministic all-vreg spill
fallback, whose argument stores now read directly from the canonical ABI input
registers.

## Consequences

The four-parameter representative callee has a zero-slot frame and no spill
traffic. AArch64 needs no entry moves because its first four ABI inputs already
match the allocator profile; x86-64 uses three scheduled moves without
clobbering `rcx` before argument four is preserved.

Physical MIR with missing, duplicate, out-of-order, or non-ABI argument markers
is rejected. This decision does not add graph coloring, five-register general
allocation, aggregate arguments, or Rust performance parity.
