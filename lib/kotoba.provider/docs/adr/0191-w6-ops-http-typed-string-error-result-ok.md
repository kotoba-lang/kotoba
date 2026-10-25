# ADR 0191: T8.3 typed-string HTTP error arm + result variant tag

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0190 response_ok; kotoba:typed host

## Context

ADR 0190 covered the `:ok` response surface (status / headers-n / body).
The `:kotoba.http/result` variant still needs the **`:error` arm**
(`code` / `message` / `retryable`) and a **variant tag** check before full
EDN encode of nested records.

## Decision

```
http_error_ok(code, message, retryable) → i64
http_result_arm_ok(arm) → i64
```

| export | codes |
|---|---|
| `http_error_ok` | `-1` code empty; `-2` code >128; `-3` code non-`[A-Za-z0-9/_:.-]`; `-4` message >65536; `-5` retryable∉{0,1}; `0` ok |
| `http_result_arm_ok` | `-1` arm∉{0,1}; `0` ok (`0`=:ok, `1`=:error) |

`main` live vector → `-13501`.

| artifact | role |
|---|---|
| `src/http_error_result_ok.kotoba` | source |
| `http-error-result-ok-v1.wasm` | kotoba-compiler wasm32 + provenance |

Registry `:http-error-result-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Code is a **string surface** (host keyword intern remains authority)
- Does **not** pack nested response/error records into one EDN blob
- Does **not** pure memory-scan one-shot of full request+result
- `:wasm-aot` stays `:partial`

## Non-claims

- Not full request/result EDN codec AOT
- Not pure Component packaging
- Not live network success

## Evidence

- browser-host `main` → `-13501n`
- digest match; exports `http_error_ok` + `http_result_arm_ok` + `main`

## Related

- T8.3; ADR 0186, 0190; residual “error/result variant”
