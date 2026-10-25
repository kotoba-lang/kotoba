# ADR 0220: T8.3 reject-path http_request_edn multi-header Component

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0219 request_edn0; kotoba-component `:http-request-edn`

## Context

ADR 0219 shipped 0-header `http_request_edn0`. The multi-header request fold
accepts a pre-built headers vector EDN (`[]` or `[{…} …]`) from
`headers_edn_append`, dual-scans url/body, gates timeout ≥ 0, and emits the
full request map string.

## Decision

1. **kotoba-component** admits `:http-request-edn` — Canonical
   `string × string × string × i64 → string` (url, headers, body, timeout-ms).
2. Ship **`http-request-edn-reject`** (wasm32 + Component) as the single-export
reject-path twin. The existing multi-export `http-request-edn-v1.wasm` package
(ADR 0209–0211) remains the host-sequenced multi-function module.

Honesty:

- Headers uniqueness remains substring scan at append time (not true set / W4).
- Does **not** multi-export full request-edn package / kit body.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- kotoba-component ≥ `ba181d08` (`:http-request-edn`)
- Component digest `5013702d…`; live wasmtime empty/multi/bad-shape
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0219; kotoba-component `:http-request-edn`
- Follow-up: multi-export kit body; true set / W4; `:wasm-aot :implemented`
