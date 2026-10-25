# ADR 0187: T8.3 typed-string http_header_name_ok (header name surface)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0182 typed URL; ADR 0186 typed request_ok; kotoba:typed host

## Context

ADR 0186 validated **url + headers-n + body + timeout** as a single typed
call but deferred **header name/value string content**. Full request EDN
codec AOT needs per-field string policy for `:kotoba.http/header` name
(token) before packing a set of headers.

## Decision

```
http_header_name_ok(name) → i64
```

| code | meaning |
|---|---|
| -1 | empty |
| -2 | length >128 |
| -3 | non-RFC-7230 tchar code point |
| 0 | ok |

**tchar** (RFC 7230 token): `ALPHA` / `DIGIT` /
`!` `#` `$` `%` `&` `'` `*` `+` `-` `.` `^` `_` `` ` `` `|` `~`.

`main` live vector → `-130`
(`Content-Type`=0, empty=-1, `Bad Name`=-3, `x-request-id`=0).

Registry `:http-header-name-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Does **not** reject JDK restricted names (`connection`, `host`, …) —
  transport still drops those quietly (host authority)
- Does **not** validate header **values** or set uniqueness
- Host http-post I/O + origin allowlist remain authority
- `:wasm-aot` stays `:partial` (full request/result EDN codec still open)

## Non-claims

- Not header value string policy
- Not pure Component packaging / memory-scan one-shot
- Not live network success

## Evidence

- browser-host `main` → `-130n`
- digest match; exports `http_header_name_ok` + `main`

## Related

- T8.3; ADR 0171, 0182, 0185, 0186
