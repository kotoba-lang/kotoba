# ADR 0245: T8.3 pure Component twin of secret_request_edn

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0236 pure secret_request_edn; kotoba-component ADR 0118
  (`:secret-request-edn`)

## Context

ADR 0236 shipped wasm32 `secret_request_edn` with live `main` → -2306.
Component packaging had no Canonical lowering (compile failed).
kotoba-component ADR 0118 admits the shape; this package re-emits it.

## Decision

| source | module (typed/wasm32) | Component (pure) |
|---|---|---|
| `secret_request_edn.kotoba` (+ main) | `:secret-request-edn` | — |
| `secret_request_edn_component.kotoba` (policy only) | — | `:secret-request-edn-component` |

1. Ship **secret-request-edn-component** sha `906d9032…`.
2. Policy export only (live main with string-length or stays on wasm32).
3. Does **not** flip secret wasm-aot to implemented (W4 + host-fetch open).

## Evidence

- wasmtime `secret-request-edn("API_TOKEN")` → `{:name "API_TOKEN"}`
- empty / quote / len>128 → empty
- ops kit registry + sha tests

## Related

- T8.3; ADR 0236/0237; component#118; W4 residual
