# ADR 0016: Verify the recursive record boundary independently

Status: accepted

The verifier pins `kotoba-native`
`8b1e22c9fb645e38ce16c3f2e24fc10468eba14d` and recognizes aggregate ABI v6.
It does not import the producer's record-admission predicate. Instead it
re-derives the one-word field family, unique qualified schemas, 32-field limit,
and new 32-level inline record nesting limit.

A nested construction/projection module is checked as KIR, executed by the
interpreter to `15`, emitted into a sealed x86-64 artifact, then independently
verified and re-emitted. A 32-level schema is admitted and a 33-level schema is
rejected, preventing the verifier from silently widening beyond the producer's
recursive boundary.

Aggregate variant payloads, indirect calls, varargs, and external linkage stay
outside the verified native boundary.
