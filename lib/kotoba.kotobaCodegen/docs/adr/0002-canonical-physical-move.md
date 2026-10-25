# ADR 0002: Canonical physical move

## Status

Accepted.

## Context

MIR can remove frame-backed phi transport when a phi edge is safe to coalesce,
including ordered moves produced by its parallel-copy scheduler. The resulting
edge copy is a physical-register operation. Allowing a
backend to infer or silently accept that copy would make MC's closed encoding
contract incomplete.

## Decision

MC v2 admits `move` as a selected instruction with the exact shape:

```clojure
{:mc/op :mc/instruction
 :mc/encoding :x86-64/move ; or :aarch64/move
 :mir/dst physical-register
 :mir/src physical-register}
```

Target namespaces must match the MC target, registers must satisfy the MIR
physical profile, and extra keys fail closed. MIR owns when and in which order a
move is safe; codegen owns its canonical selected shape; target backends own
its bytes.

## Consequences

Phi coalescing remains visible and validated across the MIR-to-MC boundary.
Unknown copies cannot bypass contract validation, and backends cannot invent a
different operand shape.
