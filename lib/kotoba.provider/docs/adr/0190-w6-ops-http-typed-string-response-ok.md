# ADR 0190: T8.3 typed-string http_response_ok (response surface)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0186 request_ok; ADR 0189 header set packing; kotoba:typed host

## Context

Request-side policy is covered through ADR 0186–0189 (URL, numeric bounds,
header name/value/pair, set packing walk). Full result EDN codec AOT still
needs the **response surface**: HTTP status range, response headers count,
and body string length — the `:ok` arm of `:kotoba.http/result` before
variant packing and error records.

## Decision

```
http_status_ok(status) → i64
http_response_ok(status, headers-n, body) → i64
```

| export | codes |
|---|---|
| `http_status_ok` | `-1` status∉[100,599]; `0` ok |
| `http_response_ok` | `-1` status; `-2` headers-n∉[0,32]; `-3` body len∉[0,65536]; `0` ok |

`main` live vector → `-1012`
(status-ok=0, status-bad=-1, response-ok=0, response-status=-1, response-headers=-2).

| artifact | role |
|---|---|
| `src/http_response_ok.kotoba` | source |
| `http-response-ok-v1.wasm` | kotoba-compiler wasm32 + provenance |

Registry `:http-response-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Does **not** walk response header name/value pairs (reuse 0189 host walk)
- Does **not** encode `:error` arm (`:code`/`:message`/`:retryable`) or full
  result variant packing
- Host transport + status canonicalization remain authority
- `:wasm-aot` stays `:partial` (error/result EDN + pure one-shot still open)

## Non-claims

- Not full request/result EDN codec AOT
- Not pure Component packaging / memory-scan one-shot
- Not live network success

## Evidence

- browser-host `main` → `-1012n`
- digest match; exports `http_status_ok` + `http_response_ok` + `main`

## Related

- T8.3; ADR 0171, 0185, 0186, 0189
- Frontier residual “response variant / status”
