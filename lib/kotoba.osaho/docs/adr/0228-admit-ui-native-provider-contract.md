# ADR 0228: Admit the native UI provider contract

## Status

Accepted.

## Decision

Native typed-feature admission accepts capability id 9 only with the exact
ui-v1 commit request and result descriptors, and id 10 only with the exact
event request and `[:option event]` result. A `:set` of a native scalar
record, and an `:option` of a native scalar record, are one-word host-table
or pair handles — the same width as `vector-i64` and `[:option :keyword]`.

`typed-set-new` / `conj` / `count` / `nth` walk like `record-new`: the type
descriptor is sealed data and is not walked as an expression.

Changing the id, either qualified type name, field order, or any nested field
keeps the call inadmissible. This is not a recursive admission of arbitrary
sets.
