# ADR-0001: Extract the checked HIR envelope before sema

- Status: accepted
- Date: 2026-08-09

## Context

The compiler already produces `:kotoba.hir/v2` and `:kotoba.hir/v3`, and
`kotoba-kir` consumes those values. The contract was implicit: lowering trusted
top-level keys, function annotations, effects, and entry/export consistency.
Moving the entire semantic analyzer first would preserve that ambiguity in a
new repository.

## Decision

`kotoba-hir` owns the versioned checked-module envelope. Validation is closed
over module and function keys and checks cross-field invariants, versioned
parameter typing, effect aggregation/ceilings, closure annotations, and the
portable representation of expression/type values.

Semantic analysis remains responsible for proving that expression operations
are admitted and well typed. HIR validation is an inter-repository contract
check, not a second source type checker.

## Consequences

`kotoba-kir` can reject malformed independently supplied HIR before lowering.
The compiler frontend can validate the artifact it produces. A later
`kotoba-sema` extraction has a concrete output contract and cannot silently add
private fields or bypass cross-field checks.
