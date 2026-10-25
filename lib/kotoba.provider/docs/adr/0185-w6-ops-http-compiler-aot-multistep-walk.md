# ADR 0185: T8.3 pure multi-step http-post bounds walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0171 http_post_bounds_ok; multi-step pattern 0179/0181/0183/0184

## Context

Http had single-shot `http_post_bounds_ok(url, headers, body, timeout)` and
typed-string URL policy (0182), but no phased pure host-walk matching
process/git multi-step packages.

## Decision

### Protocol (phases 0→1→2→3→done)

| export | success next | errors |
|---|---|---|
| `http_post_begin()` | 0 | — |
| `http_post_url(state, url_len)` | 1 | -1 url, -5 phase |
| `http_post_headers(state, n)` | 2 | -2 headers, -5 phase |
| `http_post_body(state, body_len)` | 3 | -3 body, -5 phase |
| `http_post_end(state, timeout-ms)` | 0 | -4 timeout, -5 phase |

Limits match http-v1: url 1..4096, headers 0..32, body 0..65536, timeout 1..30000.

| artifact | role |
|---|---|
| `src/http_post_walk.kotoba` | source |
| `http-post-walk-v1.wasm` | kotoba-compiler |
| `http-post-walk-v1.component.wasm` | Component |

Single-shot 0171 + typed URL 0182 retained.

### Honesty

- Host sequences phases (not pure one-shot of full request EDN)
- Network I/O still host
- `:wasm-aot` stays `:partial`

## Non-claims

- Not header name/value content scan
- Not full request/result EDN codec AOT
- Not live network success (T8.4)

## Evidence

- Node live: ok 0; bad url/headers/body/timeout -1..-4; wrong phase -5
- digest + Component

## Related

- Reliability WBS T8.3
- ADR 0171, 0182–0184
