# ADR 0002: Lower phi to dedicated merge slots

## Status

Accepted.

## Context

GMIR v2 makes value-producing control-flow explicit with block-entry phi
instructions. MIR's deterministic allocator is deliberately linear and
single-definition; pretending both branch values define one virtual register
would violate that contract, while a CFG-aware coalescing allocator would be a
much larger and target-sensitive change.

## Decision

MIR v2 preserves phi through target selection, then lowers every phi before
register allocation:

1. assign one deterministic frame slot per phi in instruction order;
2. insert a store on each named predecessor edge immediately before its jump;
3. replace the join phi with one load defining the phi destination;
4. reserve merge slots before all ordinary spill slots;
5. run the existing deterministic allocator over the rewritten single-
   definition program.

The public physical MIR contains only the existing bounded spill-load and
spill-store operations. Phi is rejected in physical MIR. GMIR/MIR v1 remains
accepted and never gains phi implicitly.

## Consequences

This is a correctness-first merge-value implementation with a predictable
eight-byte frame cost per live scalar phi. A future CFG-aware allocator may
coalesce proven-safe phis, but it must preserve this observable contract and
cannot make correctness depend on coalescing.
