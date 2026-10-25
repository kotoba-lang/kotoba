# ADR 0217: T8.3 reject-path http_result_err_edn Component

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0214 edn_quoted; kotoba-component `:http-result-err-edn`

## Context

ADR 0214–0216 shipped reject-path `edn_quoted`, `http_header_edn`, and
`headers_edn_append`. Result-variant encoding (ADR 0210) still lacks a
reject-path Component twin. The error arm is the smaller composition step:
`http_result_err_edn(code, retryable)` — quote/backslash scan on code,
retryable ∈ {0,1}, else empty.

## Decision

1. **kotoba-component** admits `:http-result-err-edn` — Canonical
   `string × i64 → string` with UTF-8 quote/backslash scan and retryable gate.
2. Ship **`http-result-err-edn`** (wasm32 + Component).

Honesty:

- Does **not** Component-re-emit `http_request_edn` / result-ok arms.
- Does **not** flip `:wasm-aot` to `:implemented`.
- Full multi-export request-edn reject package still open.

## Evidence

- kotoba-component ≥ `b2aa65c1` (`:http-result-err-edn`)
- Component digest `d7b42482…`; live wasmtime ok0/ok1/bad-atom/bad-retry
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0216; kotoba-component `:http-result-err-edn`
- Follow-up: request-edn0 / result-ok reject-path; true set / W4; multi-file kit body
