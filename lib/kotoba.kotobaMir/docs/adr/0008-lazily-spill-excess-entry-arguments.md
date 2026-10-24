# ADR 0008: Lazily spill excess function-entry arguments

## Status

Accepted. This narrows the five-live-argument fallback recorded by ADR 0007.

## Context

Both native targets expose four general allocator registers but accept five
scalar arguments in their closed call ABI. A function with five live entry
arguments therefore fell back to the all-vreg allocator, assigning a frame
slot to every SSA definition. The fallback was safe but made one unit of entry
pressure inflate the entire function frame and its load/store traffic.

The fifth ABI register is not part of the allocator profile. On x86-64 it may
also be overwritten while the first four inputs are assigned in parallel, so
the excess value must be preserved before entry copies run.

## Decision

Entry allocation keeps the first four used arguments in allocator registers.
Each additional used argument is stored directly from its canonical ABI input
register into one stable frame slot before any parallel entry copies. It is
loaded into a free allocator register only at its first use.

Straight-line callers use the same stable slot map. When a backed value is a
call argument but no allocator register is free, MIR finishes all register
copies first and loads the value directly into its outgoing ABI register. The
slot is reused when that entry value is already live across a call. Parallel
copy temporaries remain disjoint from stable slots.

If later instruction pressure cannot provide a safe register, allocation still
fails closed into the existing all-vreg path.

## Consequences

The representative five-live-argument callee and caller each use one frame
slot, one entry store, and one lazy load instead of materializing every vreg.
Four-argument functions retain their zero-slot behavior. Physical argument
markers remain exact ABI markers, so the verifier contract is unchanged.

This is bounded linear allocation, not global graph coloring. It does not claim
general spill minimization, aggregate ABI support, or Rust performance parity.
