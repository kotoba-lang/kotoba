# ADR 0197: T8.3 pure memory-scan full HTTP request one-shot

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0194 request scan; ADR 0196 header set scan

## Context

Pure slices covered URL/body/timeout (0194) and header set packing (0196)
separately. A single pure export that validates a **full request surface**
(url bytes + N header pairs + body/timeout bounds) is the host-facing
one-shot for production policy without `kotoba:typed`.

## Decision

```
http_request_full_scan(url_ptr, url_len, headers_n, table_ptr, body_len, timeout) → i32
```

| codes | meaning |
|---|---|
| `-1/-2/-3` | url empty / >4096 / not `https://` |
| `-4` | headers_n ∉ [0,32] |
| `-11/-12/-13` | name empty / >128 / non-tchar |
| `-15/-16` | value >8192 / NUL\|CR\|LF |
| `-5/-6` | body_len / timeout bounds |
| `0` | ok |

Header table layout matches ADR 0196 (n×4 i32 LE).

| artifact | role |
|---|---|
| `src/http_request_full_scan.wat` | hand source |
| `http-request-full-scan-v1.wasm` | core |
| `http-request-full-scan-v1.component.wasm` | Component embed |

Registry `:http-request-full-scan` + component; builder `:hand-wat/v1`.

### Honesty

- Does **not** flip `:wasm-aot` to `:implemented` (typed packages still
  Component-blocked; full EDN codec open)
- No header uniqueness (W4)
- Body content length-only

## Non-claims

- Not typed Component world
- Not live network success

## Evidence

- Node live vector: ok, bad scheme, bad header name, bad n, bad timeout
- digest match module + Component

## Related

- T8.3; ADR 0194–0196; pure full request residual
