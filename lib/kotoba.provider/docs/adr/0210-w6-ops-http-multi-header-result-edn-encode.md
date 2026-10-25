# ADR 0210: T8.3 multi-header append + result-variant EDN encode

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0209 fixed-depth nested EDN encode (header + request0)

## Context

ADR 0209 shipped pure EDN strings for a single header map and a 0-header
request. Residual called out multi-header sets and result variants. Full
recursive set values remain W4-gated; host-sequenced append matches the
headers-set packing walk pattern (ADR 0189) without guest set storage.

## Decision

Extend `http-request-edn-v1.wasm` (same module family):

| Export | Meaning |
|--------|---------|
| `headers_edn_empty` | `"[]"` |
| `headers_edn_append` | fold one header map into the vector EDN |
| `http_request_edn` | request with arbitrary headers EDN vector |
| `http_result_ok_edn` | `{:tag :ok :status N :headers […] :body "…"}` |
| `http_result_err_edn` | `{:tag :error :code "…" :retryable true\|false}` |
| `main` | length fingerprint **2700585195** |

Rebuild overwrites `http-request-edn-v1.wasm` (sha `eed5f689…`).

### Honesty

- Does **not** flip `:wasm-aot` to `:implemented`
- Does **not** enforce header name uniqueness (W4 set storage)
- Does **not** Component re-emit
- Does **not** claim recursive ADT identity

## Evidence

- KIR: 2-header vector, request with headers, ok/err result arms
- Package registry sha match; ops kit tests green

## Related

- T8.3; ADR 0209; packing walks 0189/0192–0193
- Follow-up: Component twin; W4 recursive values; multi-file kit body
