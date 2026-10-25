# ADR 0193: T8.3 typed-string HTTP request packing walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0182 URL; ADR 0186 request_ok; ADR 0192 result packing pattern

## Context

Result packing walk (0192) sequences the response/error variant. Request
side still had only single-shot `http_post_request_ok` (0186) and pure
length walk (0185). Symmetric **request packing walk** over typed strings
closes the host-sequenced request surface without nested EDN (W4 open).

## Decision

| export | success | errors |
|---|---|---|
| `http_request_begin()` | 0 | — |
| `http_request_url(s,url)` | 1 | `-1` empty; `-2` >4096; `-3` not `https://`; `-10` phase |
| `http_request_headers(s,n)` | 2 | `-4` n∉[0,32]; `-10` |
| `http_request_body(s,body)` | 3 | `-5` len∉[0,65536]; `-10` |
| `http_request_end(s,timeout-ms)` | 0 | `-6` timeout∉[1,30000]; `-7` incomplete; prior |

`main` live vector → `-13467`.

| artifact | role |
|---|---|
| `src/http_request_pack.kotoba` | source |
| `http-request-pack-v1.wasm` | kotoba-compiler wasm32 + provenance |

Registry `:http-request-pack`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Header **pair content** still via 0189 (not inlined in this walk)
- Does **not** pure memory-scan one-shot of request+result bytes
- Does **not** flip `:wasm-aot` to `:implemented`
- Host origin allowlist + I/O remain authority

## Non-claims

- Not full EDN encode of nested request records
- Not pure Component packaging / live network
- Not memory-scan one-shot (next residual)

## Evidence

- browser-host `main` → `-13467n`
- digest match; exports begin/url/headers/body/end + main

## Related

- T8.3; ADR 0185–0186, 0192; residual “request packing”
