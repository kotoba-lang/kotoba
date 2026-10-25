# ADR 0009: Gate the versioned native aggregate boundary

## Status

Accepted.

## Context

`kotoba-native` contract v1 makes an important distinction explicit: local
scalar record/variant SROA is admitted, while function-boundary records still
use a one-word pair-chain handle and extracted GMIR calls remain held. The
verifier already invokes the pinned native producer, so leaving its pin behind
would verify with a backend that did not publish this distinction.

## Decision

Advance the native pin to `ceca09377c53a33c4ea8bcf4a3f2e49f32cdf83d`
and consume `kotoba.native.aggregate-abi` only as a producer contract.

The verifier test requires contract version 1, the one-word pair-chain result,
host-context ownership, the 4,096-cell arena bound, and `:held` extracted
admission. It supplies every named call prerequisite and requires the native
gate to reject anyway. The verifier's own private boundary predicate remains
independently derived and is tested both positively for a scalar record and
negatively for a duplicate-field record. The established verifier remains
broader where the legacy emitter is broader, including recursively flattened
nested records; contract v1 only narrows the first future extracted crossing.

## Consequences

Producer and verifier now agree on the vocabulary and hold without making the
producer authoritative over verifier admission. No call, aggregate escape,
ownership, or Rust performance claim is added. A later ABI version must change
both the producer contract and this independent gate deliberately.
