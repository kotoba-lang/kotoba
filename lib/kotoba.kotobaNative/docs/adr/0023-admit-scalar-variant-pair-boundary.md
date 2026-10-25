# ADR 0023: Admit the scalar variant pair boundary

## Status

Accepted.

## Context

ADR 0015 deliberately kept its allocation-free `{tag,payload}` SSA bundle
inside one expression. Calling it a boundary representation would have exposed
unchecked discriminants and confused producer state with an owned runtime
value. The native runtime already has a bounded, context-owned pair arena and
uses one-word pair handles for option/result values.

The canonical KIR value is already `[type case-keyword payload]`, and the
descriptor fixes case declaration order. No new public value shape is needed.

## Decision

Advance `aggregate-abi.edn` to version 3 and admit exactly qualified, non-empty
sealed variants with at most 32 unique cases whose payload types are `:i64` or
`:bool`.

- The public host value remains `[type case-keyword payload]`.
- The guest boundary word is a context-owned handle to
  `pair(zero-based-declaration-ordinal,payload)`.
- Constructors resolve keywords to ordinals from the sealed declaration.
- Dispatch maps ordinals back through that same order and traps defensively if
  no case exists.
- Boolean payloads use only native words 0 and 1.
- The existing 4,096-cell arena and ownership lifetime apply unchanged.

For a module declaring any scalar variant parameter or result, the producer
lowers variant constructors and matches to pair allocation/projection before
GMIR. Modules with local-only variants retain ADR 0015 scalar replacement, so
admitting the boundary does not silently add allocation to that path.

## Consequences

Variant parameters and results can travel through direct calls and call-free
exports as one machine word on x86-64 and AArch64. The producer independently
rejects unknown constructors, reordered/incomplete dispatch, unqualified
identities, duplicate cases, more than 32 cases, and non-scalar payloads.

This does not admit scalar record boundaries, nested variants, record payloads,
strings, floats, refs, or a general aggregate calling convention. Host loaders
must still validate the canonical public value, ordinal range, selected payload
type, and boolean word before this becomes an executable host boundary.
