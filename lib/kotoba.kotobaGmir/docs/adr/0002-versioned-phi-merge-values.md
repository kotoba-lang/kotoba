# ADR 0002: Versioned phi merge values

## Status

Accepted.

## Context

GMIR v1 can branch and jump but cannot represent the value produced when
control-flow paths rejoin. Reusing one virtual register as the destination in
both branches would violate the single-definition contract expected by MIR
allocation, while hiding a backend copy in KIR lowering would make the generic
IR cease to describe the executed program.

## Decision

GMIR v2 adds `:gmir/phi`. Its destination is one fresh virtual register and its
canonical `:gmir/incomings` vector names every predecessor block and incoming
virtual register explicitly.

The bounded v2 contract requires:

- at least two unique incoming predecessor labels;
- the phi to occur at block entry, immediately after its join label or another
  phi;
- every incoming predecessor to be a labelled block with an explicit jump to
  that join;
- the incoming set to equal the complete set of jumps to the join;
- no conditional critical edge or implicit fallthrough into the phi block.

GMIR v1 remains accepted and continues to reject phi. Consumers must opt into
v2 rather than silently changing the closed v1 operation set.

## Consequences

MIR can lower phi edges deterministically without guessing control-flow
ownership. More general critical-edge splitting remains outside this bounded
contract and fails closed.
