# ADR 0188: T8.3 typed-string HTTP header value + pair policy

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0187 header name_ok

## Context

ADR 0187 validated header **names** (RFC 7230 tchar). Header **values** and
name+value **pair** compose remained open for request EDN codec AOT.

## Decision

| export | codes |
|---|---|
| `http_header_value_ok` | `-2` >8192, `-3` NUL/CR/LF, `0` ok (empty allowed) |
| `http_header_pair_ok` | name `-1/-2/-3` first; value `-2→-5`, `-3→-6` |

`main` live vector → `-3036`.

Registry `:http-header-value-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Pair re-checks name with same tchar rules as 0187 (not a cross-module call)
- Does not implement full header set EDN encode
- `:wasm-aot` stays `:partial`

## Non-claims

- Not full request/result EDN codec
- Not pure Component
- Not live network

## Evidence

- browser-host `main` → `-3036n`
- digest match

## Related

- T8.3; ADR 0186–0187
