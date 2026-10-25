# ADR 0189: T8.3 typed-string HTTP header set packing walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0187 name_ok; ADR 0188 value/pair

## Context

ADR 0187–0188 validated single header **name** and **value/pair**. Full
request EDN codec needs host-sequenced **set packing** of up to 32 pairs
without recursive header-set values (W4 still open).

## Decision

Host-walk protocol (remaining-count state):

| export | success | errors |
|---|---|---|
| `http_headers_begin(n)` | remaining=`n` | `-4` n∉[0,32] |
| `http_headers_pair(state,name,value)` | remaining-1 | prior; `-8` extra; name `-1/-2/-3`; value `-5/-6` |
| `http_headers_end(state)` | `0` | prior; `-7` incomplete |

Pair policy matches 0188 (RFC 7230 tchar name; value no NUL/CR/LF, ≤8192).

`main` live vector → `-3647`
(empty=0, one=0, bad-name=-3, bad-value=-6, bad-n=-4, incomplete=-7).

| artifact | role |
|---|---|
| `src/http_headers_set_ok.kotoba` | source |
| `http-headers-set-ok-v1.wasm` | kotoba-compiler wasm32 + provenance |

Registry `:http-headers-set-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Host sequences pairs; not a recursive set value in guest memory
- **Does not** check name uniqueness (needs set storage / W4)
- Does not encode response variant / full request EDN
- `:wasm-aot` stays `:partial`

## Non-claims

- Not full request/result EDN codec AOT
- Not pure Component packaging / memory-scan one-shot
- Not live network; not JDK restricted-name list

## Evidence

- browser-host `main` → `-3647n`
- digest match; exports begin/pair/end + main

## Related

- T8.3; ADR 0186–0188; frontier residual “header set packing”
