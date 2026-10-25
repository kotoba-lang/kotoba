# ADR 0018: Independently verify the native UI provider contract

## Status

Accepted.

## Decision

The verifier accepts typed capability ids 9 and 10 only when their request
and result descriptors exactly reproduce ui-v1, including qualified names,
declaration order, and every nested field type. It independently admits
`[:set record]` and `[:option record]` as one-word values, skips the type
descriptor on `typed-set-*`, remembers a `typed-cap-call` record result for
`record-get`, and binds an `option-match` some-arm to the event record schema.

It does not import the producer predicate or infer the contract from a
numeric kind emitted by the backend.
