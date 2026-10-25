# ADR 0013: Verify bounded lazy function-entry spills

## Status

Accepted.

## Decision

Pin native merge `eeae98511a574a1be1280b3b3fbdaa1fbdd6efed` and
independently compile a five-parameter local scalar call for x86-64 and
AArch64. Both functions must retain all five exact ABI input markers while
declaring policies `[:allocator :call-live]` and frame slots `[1 1]`.

Each function must contain exactly one direct entry store from the fifth ABI
input and exactly one slot-zero load. In the caller, that load must target the
fifth outgoing ABI register immediately before the call. Any return to the
all-vreg policy or whole-function materialization fails this gate.

## Consequences

The verifier now checks the producer's bounded five-argument behavior instead
of relying on native documentation or byte counts. The existing four-argument
zero-frame gate remains independent. This does not widen aggregate or external
call admission and does not establish Rust performance parity.
