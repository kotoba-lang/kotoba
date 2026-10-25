# ADR 0007: verify local record scalar replacement independently

- Status: accepted
- Date: 2026-08-11

## Context

`kotoba-native` can scalar-replace a non-escaping fixed record across a
value-position `if`, but the verifier previously remembered a record schema for
only a direct constructor or a boxed call result. A valid source therefore
compiled in the producer and was rejected before artifact admission.

## Decision

The verifier pins native `8374a6c4cdd31110363a6996eaba6a737d9d9f02` and
independently recognizes one additional value shape: an `if` whose two branches
are direct `record-new` forms of the same exact non-empty fixed record, with
unique keyword fields whose types are only `:i64` or `:bool`. That value may be
projected directly or named by one `let` before projection.

Each branch is still recursively verified, including the condition and every
constructor field. A later `record-get` must use the exact schema and a declared
field. The verifier does not infer aggregate types generally and does not trust
producer metadata for this decision.

## Consequences

The verifier and producer agree on the first record SROA family while retaining
fail-closed behavior for mismatched branches, string/option/result fields,
nested records, symbol forwarding, escaping records, variants, and a general
aggregate ABI. This is not Rust-wide performance-parity evidence.
