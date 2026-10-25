# ADR 0026: Remove production legacy routing

Status: accepted

## Decision

Both production native entry points now augment checked KIR helpers and invoke
the whole-module KIR → GMIR → MIR → MC pipeline unconditionally. An IR
rejection propagates as a fail-closed result; it cannot select either retired
recursive ISA expression emitter.

Whole-module lowering accepts one or more declared exports. GMIR retains the
first export as its entry identity, while final native layout publishes exact
offset, length, and arity metadata for every requested export.

The dynamic test compatibility seam is removed. Public emitters have exactly
one route, and tests for held nested/non-scalar aggregate representations now
assert the same fail-closed production boundary rather than executing retired
recursive code.

## Consequences

- Every production native operation crosses versioned GMIR, target-selected
  MIR, allocated MC, and the closed target encoder.
- Unknown operations and held value shapes fail before ISA emission.
- Multi-export modules no longer require the old layout path.
- Retired emitter code has no public or test routing switch.
