# ADR 0036: Seal `:vector-i64` from body ops (T4.5 / T1.3)

- Status: Accepted
- Date: 2026-07-29
- WBS: T4.5 / T1.3

## Context

Pure-product programs that build a temporary `vector-i64` and only export an
i64 result (e.g. `(vector-count (vector-i64 1 2 3))`) failed wasm emit with
`typed Wasm descriptor is not sealed :vector-i64`. Exporting a
`:vector-i64` function sealed the type; body-only use did not.

`vector-f64-*` ops already contributed to `descriptor-table` via `walk`.

## Decision

When walking KIR for descriptor sealing, treat `vector-new` / `vector-count` /
`vector-get` / `vector-at` / `vector-drop` / `vector-assoc` / `vector-conj` as
producing/using `:vector-i64` (same pattern as vector-f64).

## Evidence

- Dual-backend pure-product pilot `:vector-i64-kit` (compiler follow-up)
