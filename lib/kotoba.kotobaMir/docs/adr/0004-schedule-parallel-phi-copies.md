# ADR 0004: Schedule parallel phi copies

## Status

Accepted. This completes the no-spill multi-phi case left open by ADR 0003.

## Context

Several phis at one join are simultaneous assignments on every predecessor
edge. Emitting them as an arbitrary sequence of register moves is incorrect:
a move may destroy a source needed by a later assignment. ADR 0003 therefore
kept all multi-phi edges frame-backed even when register allocation succeeded.

The conservative representation is safe but allocates one eight-byte slot per
phi and performs one store per predecessor plus one join load per phi. Most
multi-phi edges are acyclic or contain only a small register permutation.

## Decision

After no-spill allocation, MIR treats every complete merge-store run directly
before its edge jump as a parallel copy. A join is eligible only when every phi
slot has exactly one load and at least two predecessor stores. Incomplete or
malformed groups retain the ADR 0002 frame representation; MIR never partially
rewrites a join.

For an eligible edge, MIR repeatedly emits the first copy whose destination is
not a source of another pending copy. Self-copies are removed. This order is
deterministic and preserves every source value for acyclic graphs.

If no copy is ready, the pending graph contains a cycle. MIR stores the first
source in one temporary frame slot, replaces uses of that source with the
temporary, and continues. The temporary slot is reusable across all mutually
exclusive predecessor edges. Restoring it is an ordinary physical
`:mir/spill-load`; no new MIR or MC operation is introduced.

General register-pressure spilling remains unchanged: phi destinations own
ordinary spill slots and predecessor edges store directly into those slots.

## Consequences

Acyclic multi-phi joins use zero phi frame bytes and only the required physical
moves. A cyclic join uses one eight-byte temporary regardless of the number of
phis, with one store/load pair per cycle. The scheduler is exhaustively tested
against all 256 source mappings of each four-register target profile. x86-64 and
AArch64 continue to consume the same closed physical MIR operations.
