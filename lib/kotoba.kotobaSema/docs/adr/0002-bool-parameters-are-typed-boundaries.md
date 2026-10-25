# ADR-0002: Boolean parameters are typed boundaries

- Status: accepted
- Date: 2026-08-11

## Context

Compatibility HIR may omit `:param-types` when every parameter is an `:i64`.
The selection test treated `:bool` like an untyped 0/1 literal, so a library
whose only typed feature was `[enabled :bool]` emitted compatibility HIR and
silently reconstructed that parameter as `:i64` downstream.

## Decision

A declared `:bool` parameter selects typed HIR and retains the complete
`:param-types` vector. A boolean expression or result alone does not force the
migration; compatibility programs without a typed parameter remain HIR v2.

## Evidence

The sema suite proves both sides of the boundary. Removing `:bool` from the
typed-parameter selection set makes two assertions fail: the output falls from
HIR v3 to v2 and the parameter table disappears.

## Consequences

KIR and native consumers can distinguish host booleans from integer words for
entryless exported functions. This does not add a new boolean representation
inside generated machine code.
