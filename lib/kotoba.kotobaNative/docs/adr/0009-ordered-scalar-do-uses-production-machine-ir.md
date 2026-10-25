# ADR-0009: Ordered scalar `do` uses production machine IR

**Status:** accepted and implemented
**Date:** 2026-08-11

## Context

The production GMIR/MIR/MC route covered scalar expressions, lexical `let`,
and tail conditionals, but a scalar `do` still selected the established direct
emitter. Treating all but the final expression as dead would be incorrect:
Kotoba evaluates `do` left to right, and an unused expression such as `quot`
can still trap.

## Decision

Admit a non-empty scalar `do` into the production route. Lower every child in
source order into the same GMIR instruction stream and return only the final
child's virtual register. No dead-code elimination is performed at this
boundary. Empty `do`, whose value is `nil`, remains outside the i64/bool slice
and fails closed.

The change adds no operation to GMIR, MIR, or allocated MC. It composes their
existing closed contracts and therefore does not create a second sequencing
or effect model in the native repository.

## Consequences

- Both native ISAs use GMIR -> MIR -> deterministic allocation -> MC -> final
  layout for admitted scalar `do` bodies.
- Intermediate expressions remain ordered and observable traps are preserved.
- Unsupported children reject production routing as a whole; there is no
  partial IR/direct-emitter mixture inside one function.

## Verification

Tests assert instruction order, production routing, final-byte integration for
both ISAs, preservation of x86-64 `IDIV` and AArch64 guarded `SDIV`/`BRK`, and
fail-closed rejection of empty `do`.
