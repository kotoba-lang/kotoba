# ADR 0192: T8.3 typed-string HTTP result packing walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0190 response_ok; ADR 0191 error/result tag; kotoba:typed host

## Context

Field policies for request (0186–0189) and result arms (0190–0191) exist as
separate surfaces. Full result EDN codec still needs a **host-sequenced packing
walk** that composes the active variant arm without recursive nested values
in guest memory (W4 open; max-params 5).

## Decision

Host-walk protocol after variant tag:

| export | success | errors |
|---|---|---|
| `http_result_begin(arm)` | ok→1 / error→11 | `-1` arm∉{0,1} |
| `http_result_status(s,status)` | 2 | prior; `-10` phase; `-2` status∉[100,599] |
| `http_result_headers(s,n)` | 3 | prior; `-10`; `-3` n∉[0,32] |
| `http_result_body(s,body)` | 4 | prior; `-10`; `-4` body len |
| `http_result_code(s,code)` | 12 | prior; `-10`; `-5/-6/-7` code |
| `http_result_message(s,msg)` | 13 | prior; `-10`; `-8` msg len |
| `http_result_retryable(s,r)` | 14 | prior; `-10`; `-9` r∉{0,1} |
| `http_result_end(s)` | 0 | prior; `-11` incomplete |

`main` live vector → `-12061`
(ok-pack=0, bad-arm=-1, bad-status=-2, err-pack=0, empty-code=-5, incomplete=-11).

| artifact | role |
|---|---|
| `src/http_result_pack.kotoba` | source |
| `http-result-pack-v1.wasm` | kotoba-compiler wasm32 + provenance |

Registry `:http-result-pack`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Host sequences fields; guest does not hold a recursive result value
- Does **not** pure memory-scan one-shot of request+result bytes
- Does **not** flip `:wasm-aot` to `:implemented`
- Keyword intern for error codes remains host authority (string surface)

## Non-claims

- Not full EDN encode/decode of nested records
- Not pure Component packaging / live network
- Not request-side packing walk (separate residual)

## Evidence

- browser-host `main` → `-12061n`
- digest match; exports begin/status/headers/body/code/message/retryable/end + main

## Related

- T8.3; ADR 0185 walk pattern; 0190–0191; residual “nested EDN pack”
