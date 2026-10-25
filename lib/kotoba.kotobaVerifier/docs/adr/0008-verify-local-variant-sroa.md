# ADR 0008: verify local variant scalar replacement independently

## Status

Accepted.

## Context

`kotoba-native` now scalar-replaces a non-escaping sealed variant whose case
payloads are all `:i64` or `:bool`. Construction becomes an internal tag and
payload SSA bundle, a variant-valued `if` emits two phis, and a match becomes
target-neutral comparison control flow.

The verifier already admitted the older directly nested `variant-new` /
`variant-match` contract, including wider legacy payload representations. It
did not remember a local variant schema, so admitting arbitrary variant symbols
would have trusted producer inference instead of independently bounding it.

## Decision

The verifier independently defines the scalar-replaced variant family and
remembers a local variant descriptor only when its binding is:

1. a direct `variant-new` of an all-`:i64`/`:bool` sealed variant; or
2. one `if` whose arms are direct constructors of that identical schema.

A match is admitted only when its operand independently resolves to the exact
declared schema and its branches cover every case in declaration order. The
verifier checks constructor payloads, conditions, and every branch body through
the ordinary hostile-KIR expression walk.

The existing directly nested legacy match remains admitted for its established
payload family. A second symbol binding is not resolved. Non-scalar or nested
local payloads, mismatched branch schemas, malformed cases, variant parameters,
and variant results remain rejected by this gate or the native boundary checks.

The verifier pins kotoba-native at the producer merge containing the matching
implementation, so verification re-emits through the same closed dependency
revision without importing producer predicates.

## Consequences

The verifier and producer agree on the local scalar variant slice while their
admission logic remains independently implemented. This does not establish an
aggregate function-boundary ABI or general aggregate inference.
