# ADR 0186: T8.3 typed-string http_post_request_ok (request surface slice)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0171 pure bounds; ADR 0182 typed URL; ADR 0185 multi-step walk

## Context

Http had pure numeric bounds (0171), multi-step walk (0185), and typed URL
(0182) as separate surfaces. A single typed-string call that validates
**url + headers-n + body + timeout** is the next step toward request
codec AOT without full EDN encode/decode.

## Decision

```
http_post_request_ok(url, headers-n, body, timeout-ms) → i64
```

| code | meaning |
|---|---|
| -1 | url empty |
| -2 | url >4096 |
| -3 | not `https://` |
| -4 | headers-n ∉ [0,32] |
| -5 | body length ∉ [0,65536] |
| -6 | timeout-ms ∉ [1,30000] |
| 0 | ok |

`main` live vector → `-13406`.

Registry `:http-post-request-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Does **not** validate header name/value strings or EDN shape
- Host http-post I/O + SSRF allowlist remain authority
- `:wasm-aot` stays `:partial` (full request/result EDN codec still open)

## Non-claims

- Not full EDN codec AOT
- Not pure Component packaging
- Not live network success

## Evidence

- browser-host `main` → `-13406n`
- digest match; exports `http_post_request_ok` + `main`

## Related

- T8.3; ADR 0162, 0165, 0171, 0182, 0185
