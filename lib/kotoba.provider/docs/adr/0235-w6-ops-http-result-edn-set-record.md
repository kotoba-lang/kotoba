# ADR 0235: T8.3 result-variant EDN from kit-shaped set-record

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0233 headers fold; ADR 0234 request full EDN; compiler 0194

## Context

Kit result is a variant with ok (status + headers set + body) and
error (code + message + retryable). Prior pure packages had string-only
result arms (0217/0218) without kit-shaped set-of-header-records on ok.

## Decision

1. Ship **http-result-edn-set-record** (wasm32, kotoba:typed):
   - ok guest record with status, set-of-header-records + name-set,
     body; EDN via typed-set-nth fold
   - error fixed-depth http_res_err_edn(code, message, retryable)
   - main → **-9002**
2. Code/message are pure strings (not keywords); retryable is i64 0/1.
3. Fixed-depth variant arms only — not W4 recursive nested EDN ADT.
4. Does not flip wasm-aot to implemented.

## Evidence

- Package sha 954b1bff…; KIR main → -9002
- ops kit registry + sha tests

## Related

- T8.3; ADR 0231–0234; W4 residual remains
