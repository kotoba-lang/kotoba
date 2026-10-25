# ADR 0012: Encode coalesced phi edge moves

## Status

Accepted. This refines ADR 0011's transport cost without changing its control-
flow semantics.

## Context

MIR now proves when a single-phi join can replace dedicated frame transport
with physical edge moves. The selected MC contract names those moves exactly.
The native backend must encode that closed operation on both supported ISAs;
falling back to the legacy emitter or reconstructing phi semantics would split
ownership and could execute the wrong branch.

## Decision

- `:x86-64/move` encodes a 64-bit register-to-register `mov`.
- `:aarch64/move` encodes the existing 64-bit register alias operation.
- A self-move emits no bytes.
- Unknown encodings and non-canonical operands continue to fail in MC before
  byte encoding.
- Frame-backed spill load/store encoding remains unchanged for multi-phi joins
  and other non-coalesced programs.

## Consequences

The common value-position scalar `if` reaches final x86-64 and AArch64 bytes
with zero phi frame bytes and no phi memory traffic. Correctness still rests on
GMIR's explicit predecessor contract and MIR's safe fallback, not on this
optimization.
