# ADR 0219: T8.3 reject-path http_request_edn0 Component

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0214 edn_quoted; kotoba-component `:http-request-edn0`

## Context

ADR 0214–0218 shipped reject-path `edn_quoted`, header map, headers append,
result-err, and result-ok. The 0-header request fold (`http_request_edn0`) is the next
composition step before multi-header `http_request_edn`: dual-scan url/body,
timeout-ms ≥ 0, decimal timeout, fixed empty headers vector.

## Decision

1. **kotoba-component** admits `:http-request-edn0` — Canonical
   `string × string × i64 → string`.
2. Ship **`http-request-edn0`** (wasm32 + Component).

Honesty:

- Does **not** multi-header / uniqueness / result-ok multi-export package.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- kotoba-component ≥ `1325aa15` (`:http-request-edn0`)
- Component digest `c249a623…`; live wasmtime ok/zero/neg/bad-atom
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0218; kotoba-component `:http-request-edn0`
- Follow-up: multi-header request-edn; true set / W4; multi-file kit body
