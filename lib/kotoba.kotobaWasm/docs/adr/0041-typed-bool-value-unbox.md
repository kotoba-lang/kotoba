# ADR 0041: typed-bool-value — unbox host boolean to i32 0/1 word

- Status: Accepted
- Date: 2026-07-30
- Related: compiler ADR 0191 A (language profile 5)

## Decision

Add host import `kotoba:typed/bool-value` with type
`(param externref) (result i32)` — the inverse of `kotoba:typed/bool`
`(param i32) (result externref)`.

Intrinsic name: `typed-bool-value`.

## Why

Profile 5 carries `:bool` as a plain 0/1 word inside modules, while aggregate
slots (record/vector fields) continue to store sealed JS booleans. Reading a
`:bool` field needs unboxing; writing already boxes via `typed-bool`.

## Status note (2026-07-31)

The import is **always-on** for typed modules: emit-get for `:bool` fields
uses `typed-bool-value`, and host `browser-host` / `bool-value` companions
are landed (compiler#449/#451, wasm#42/#44). The old `has-bool-value? false`
gate was dead code (duplicate of the base import list) and was removed.
