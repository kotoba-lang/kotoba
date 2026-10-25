# ADR 0010: Verify scalar direct-call frames

## Status

Accepted.

## Context

Native aggregate contract v1 held every extracted call because the machine IR
had no canonical per-function frame, call-clobber, argument-assignment, or
return-register contract. Native contract v2 adds those rules for scalar direct
calls. Aggregate values still do not cross the extracted boundary.

The verifier invokes the native emitter from its own dependency closure. Its
pin and independent gate therefore have to advance with the producer; accepting
the version number alone would not prove that a real two-function module can be
re-emitted.

## Decision

Pin `kotoba-native` merge `228e389ccc449d6256a7f6ba0b623203e0a439d9`.
Require contract v2, the exact four call guarantees, scalar call admission, and
continued holds for record and variant boundaries. For both native targets the
gate must admit the complete guarantee set and reject a set missing live-value
preservation.

Independently build, seal, and verify a KIR module whose caller keeps a scalar
live across a direct call. Re-emission equality uses the pinned production
x86-64 emitter rather than a synthetic byte fixture.

## Consequences

The verifier can now detect producer drift in scalar direct-call lowering and
continues to fail closed when any frame guarantee is absent. This does not
admit indirect calls, recursion, calls with aggregate parameters/results, or
aggregate escape. It also makes no Rust-equivalent performance claim.

ADR 0009 remains the historical record for contract v1 and is superseded only
for scalar call admission; its aggregate holds remain in force.
