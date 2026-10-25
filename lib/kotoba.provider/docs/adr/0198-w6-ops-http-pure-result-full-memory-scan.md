# ADR 0198: T8.3 pure memory-scan full HTTP result one-shot

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0194 result/error scans; ADR 0196 header set scan; ADR 0197 full request

## Context

Full **request** pure one-shot landed in ADR 0197. Result still had separate
response/error numeric scans (0194) without a single export that sequences
variant arm + response headers table or error code bytes.

## Decision

```
http_result_full_scan(arm, status, headers_n, table_ptr, body_len,
                      code_ptr, code_len, msg_len, retryable) → i32
```

| arm | codes |
|---|---|
| bad | `-1` arm∉{0,1} |
| ok (0) | `-2` status; `-4` headers_n; `-11/-12/-13` name; `-15/-16` value; `-3` body |
| error (1) | `-21/-22/-23` code; `-24` msg_len; `-25` retryable |
| | `0` ok |

Header table layout matches ADR 0196.

| artifact | role |
|---|---|
| `src/http_result_full_scan.wat` | hand source |
| `http-result-full-scan-v1.wasm` | core |
| `http-result-full-scan-v1.component.wasm` | Component embed |

Registry `:http-result-full-scan` + component; builder `:hand-wat/v1`.

### Honesty

- Does **not** flip `:wasm-aot` to `:implemented` (typed Component world open)
- No header uniqueness (W4)
- Body content length-only on ok arm

## Non-claims

- Not typed Component packaging
- Not live network

## Evidence

- Node live: ok arm, bad status, error arm ok, empty code, bad arm
- digest match module + Component

## Related

- T8.3; ADR 0194–0197; pure full result residual
