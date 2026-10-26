# ADR 0227: Seal the first native provider contract

## Status

Accepted.

## Decision

Native typed-feature admission accepts capability id 7 only with the exact
clock-v1 request and result descriptors. The request is a two-case boolean
variant; the result is the three-case variant of the wall, monotonic, and typed
error records defined by the capability kit.

Changing the id, either qualified type name, case order, or any nested field
keeps the call inadmissible. This is the first production provider contract,
not a recursive admission of arbitrary host aggregates.
