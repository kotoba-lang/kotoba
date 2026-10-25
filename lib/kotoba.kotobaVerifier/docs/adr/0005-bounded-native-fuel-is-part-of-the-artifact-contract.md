# ADR 0005: bounded native fuel is part of the artifact contract

- Status: Accepted
- Date: 2026-08-09

## Context

Native artifacts carried both `:limits :fuel` and `:fuel-abi :initial`, but the
verifier required both to equal 512 and independently evaluated the entry with
the KIR interpreter's default 512 fuel. The compiler already accepts an
explicit bounded emit budget, and native hosts carry the initial fuel in the
hidden execution context. Consequently a valid bounded parser could execute
under its declared host budget but could not be sealed or verified.

## Decision

The native artifact's fuel value is admitted when it is an integer from 1
through 1,048,576 inclusive. `:limits :fuel` and `:fuel-abi :initial` must be
identical. The verifier's independent KIR oracle uses that exact declared
value. Memory, stack, context layout, and all other ABI limits remain fixed.

The default remains 512. Raising fuel is therefore explicit, sealed into the
artifact identity, verifier-bounded, and visible to the tender; it is never an
ambient or replenishable allowance.

## Consequences

- a tender must provide the sealed initial fuel value;
- mismatched, zero, negative, non-integer, or over-limit values fail closed;
- higher fuel does not enlarge string, pair, vector, memory, or stack arenas.
