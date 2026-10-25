# ADR 0011: Verify liveness-minimal call frames

## Status

Accepted.

## Context

ADR 0010 admitted scalar direct calls using the producer's correctness-first
all-vreg frame. The producer now has a distinct `:call-live` policy that saves
only values live across a straight-line call while retaining all-vregs as a
safe fallback.

## Decision

Pin native merge `30d4a1fb6f1ccc4e52d5abd11852a7fecf8bcab8`, which
contains ADR 0018. In addition to artifact
re-emission equality and aggregate ABI v2, independently compile the
representative two-function KIR module for x86-64 and AArch64.

Require its caller to declare `:call-live`, own exactly one frame slot, and
contain exactly one spill store and one spill load. Continue requiring the
complete call guarantee set and the record/variant boundary holds.

## Consequences

The verifier detects a producer regression back to all-definition spilling or
an accidental loss of the live value. CFG liveness, slot coloring, indirect
calls, recursion, and aggregate call boundaries remain outside this gate.
