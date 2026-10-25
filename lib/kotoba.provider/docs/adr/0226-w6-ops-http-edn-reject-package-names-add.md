# ADR 0226: T8.3 multi-export reject package folds true-set names-add

- Status: Accepted
- Date: 2026-08-01
- Depends: kotoba-component multi-export + `:headers-names-add` (`d931faca`);
  ADR 0222, 0225

## Context

ADR 0222 multi-export reject kit body (empty + append + request + results)
and ADR 0225 single-export Component twin for true-set **name lists** were
separate packages. Hosts needed both on **one shared-memory Component**.

## Decision

1. **kotoba-component** optional role `:headers-names-add` on
   `:http-edn-reject-package` (shared `has-name-element`).
2. Re-ship **`http-edn-reject-package`** with six exports: empty, append,
   **names-add**, request, result-ok, result-err.

Honesty:

- Append uniqueness remains marker scan for **header maps**; names-add is the
  true-set **name-list** plane on the same Component.
- Does **not** flip `:wasm-aot :implemented` (W4 recursive nested EDN open).

## Evidence

- kotoba-component ≥ `d931faca`
- Component digest `0befd905…`; wasmtime names-add Host/dup + append
- ops kit registry + sha tests

## Related

- T8.3; ADR 0221–0225
- Follow-up: W4 recursive EDN; only then `:wasm-aot :implemented`
