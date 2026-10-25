# ADR 0012: Verify parallel function-entry assignment

## Status

Accepted. The four-argument gate remains current; ADR 0013 adds the bounded
five-argument gate.

## Decision

Pin native merge `7f2120deade9425d7920689b88119790f4bdcea9` and
independently compile a four-parameter local scalar call for x86-64 and
AArch64. Require exact ABI input markers in both functions, zero callee and
caller frame slots, and no spill instructions.

The x86-64 callee must contain three entry moves; the AArch64 callee must
contain none. This count combines with exact marker and no-spill assertions to
detect lost entry assignment or regression to the conservative fallback.

## Consequences

The verifier closes the producer pin against the same entry ABI property rather
than trusting documentation or a code-size observation. Five-live-parameter
fallback, aggregate calls, external calls, and Rust performance parity are not
widened by this gate.
