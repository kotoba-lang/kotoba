# ADR 0194: T8.3 pure memory-scan one-shot HTTP request+result

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0186 request bounds; ADR 0190–0191 result arms; ADR 0163/0169 hand WAT pattern

## Context

Typed packing walks (0192–0193) and field policies (0182–0191) cover host-fed
typed strings and multi-step sequences. Secret/scoped-fs still retain pure
**ptr/len memory-scan** one-shots (`secret_name_ok`, `fs_path_ok`). HTTP had
only pure **length** bounds (0171) and typed surfaces — no pure memory-scan of
URL/code **bytes** in linear memory without `kotoba:typed`.

## Decision

Hand WAT core module (exports `memory`) with pure i32 ABI:

| export | role |
|---|---|
| `http_request_scan(url_ptr,url_len,headers_n,body_len,timeout)` | scan `https://` prefix + numeric bounds |
| `http_response_scan(status,headers_n,body_len)` | ok-arm status/headers/body-len |
| `http_error_scan(code_ptr,code_len,msg_len,retryable)` | scan code charset + msg/retry bounds |
| `http_result_arm_ok(arm)` | arm ∈ {0,1} |

Request codes: `-1` empty url, `-2` url>4096, `-3` not https, `-4` headers_n,
`-5` body_len, `-6` timeout, `0` ok.

Response codes: `-1` status, `-2` headers_n, `-3` body_len, `0` ok.

Error codes: `-1` empty code, `-2` code>128, `-3` bad char, `-4` msg_len,
`-5` retryable, `0` ok.

| artifact | role |
|---|---|
| `src/http_memory_scan.wat` | hand source |
| `http-memory-scan-v1.wasm` | assembled core |
| `http-memory-scan-v1.component.wasm` | `wasm-tools component new` embed |

Registry `:http-memory-scan` + `:http-memory-scan-component`.
Builder `:hand-wat/v1` (not kotoba-compiler). No `kotoba:typed` import.

### Honesty

- Does **not** encode nested EDN records or header set uniqueness
- Does **not** flip `:wasm-aot` to `:implemented` (typed Component world still open)
- Body content is length-only (no body charset policy)
- Host still owns I/O + origin allowlist

## Non-claims

- Not typed-string packaging replacement
- Not live network success
- Not retirement of 0171/0192/0193 surfaces

## Evidence

- Node WebAssembly: request/response/error scan vectors match codes
- digest match module + Component
- no `kotoba:typed` import

## Related

- T8.3 residual “pure memory-scan one-shot”
- ADR 0163 secret hand scan; 0169 scoped-fs hand scan; 0171 pure bounds
