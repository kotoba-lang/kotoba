# ADR 0218: T8.3 reject-path http_result_ok_edn Component

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0217 result_err_edn; kotoba-component `:http-result-ok-edn`

## Context

ADR 0217 shipped reject-path `http_result_err_edn`. The matching ok arm
`http_result_ok_edn(status, headers, body)` needs status decimal (0–999),
headers `[…]` shape gate, and body quote/backslash reject — the last pure
result surface before full multi-export request composition.

## Decision

1. **kotoba-component** admits `:http-result-ok-edn` — Canonical
   `i64 × string × string → string` with status ∈ [0,999] decimal, headers
   shape, body scan. WAT owns semantics.
2. Ship **`http-result-ok-edn`** (wasm32 + Component).

Honesty:

- Does **not** Component-re-emit full multi-export `http_request_edn`.
- Does **not** flip `:wasm-aot` to `:implemented`.
- Does **not** claim W4 set uniqueness.

## Evidence

- `kotoba compile --target component` with kotoba-component ≥ `4344df77`
- Component digest `1d061693…`; live wasmtime ok/bad-status/bad-body/bad-headers
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0217; kotoba-component `:http-result-ok-edn`
- Follow-up: http_request_edn reject-path; multi-export package; true set / W4
