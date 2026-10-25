# ADR 0010: Ordered `do` delegates final tail control

## Status

Accepted.

## Context

The production machine-IR route admitted ordered non-empty scalar `do` and
nested tail `if` separately. A function whose final `do` expression was an
`if` therefore remained on the established emitter even though both component
semantics were already representable by the closed GMIR/MIR contracts.

Treating every `do` child as a value is incorrect for this shape. A tail `if`
has two returning paths and deliberately has no merge value. Moving or dropping
the preceding expressions is also incorrect because an unused operation such
as signed `quot` may trap.

## Decision

For a non-empty `do` in tail position:

1. lower every expression except the last through scalar value lowering, in
   source order;
2. retain all emitted instructions, including unused trapping operations;
3. lower the last expression through tail lowering;
4. continue to reject a non-final `if`, because value-position control needs a
   separate merge-value contract;
5. keep empty `do` outside the i64/boolean scalar contract because its value is
   `nil`.

This introduces no new GMIR, MIR, allocation, MC, or layout operation. Both
branch arms keep their direct returns and final layout remains the sole owner of
branch displacement resolution.

## Consequences

`(do prefix... (if test then else))`, including recursively nested tail `do`,
uses the production KIR -> GMIR -> MIR -> allocated MC -> layout path on x86-64
and AArch64. Value-position `if` remains explicitly unsupported rather than
being partially mixed with the established emitter.
