# ADR 0014: Verify the scalar variant boundary independently

## Status

Accepted.

## Context

kotoba-native aggregate ABI v3 admits a narrow scalar variant boundary. Merely
reading the producer's predicate would make producer and verifier agree on the
same mistake, especially around case count, declaration order, and payload
families.

## Decision

Pin the producer containing ABI v3 and independently admit only qualified
variants with 1--32 unique ordered cases and `:i64`/`:bool` payloads.

Variant-typed parameters carry their exact schema in the verifier environment.
A call carries a variant schema only when the callee's sealed result is in the
same narrow family. `variant-match` still requires the exact type and exactly
one branch per case in declaration order. Exported parameters/results use the
same predicate; the broader local variant family does not leak through it.

Re-emission through the pinned x86-64 producer proves that the independently
accepted KIR is also executable input to the production backend. Negative tests
cover non-boundary payloads and reordered dispatch.

## Consequences

The verifier no longer rejects a valid scalar variant merely because it entered
through a parameter or direct-call result, while malformed or broader variants
remain fail closed. This does not validate host loader tokens or supervisor
reports; those remain downstream obligations.
