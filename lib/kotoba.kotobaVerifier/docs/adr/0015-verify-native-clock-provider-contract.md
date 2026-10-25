# ADR 0015: Independently verify the native clock provider contract

## Status

Accepted.

## Decision

The verifier accepts typed capability id 7 only when its request and result
descriptors exactly reproduce clock-v1, including qualified names, declaration
order, and every nested field type. It does not import the producer predicate
or infer the contract from a numeric kind emitted by the backend.
