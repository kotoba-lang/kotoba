# ADR 0232: T8.3 fixed-depth secret reply EDN encode

- Status: Accepted
- Date: 2026-08-01
- Depends: secret_name_ok pure Component (0206); HTTP result EDN arms (0217/0218)

## Context

Secret kit `:result` is
`[:variant :kotoba.secret/reply [[:value :string] [:error record]]]`.
Name policy AOT is landed (0173–0206); **reply codec AOT** remained open
(kit-readiness: wasm-aot partial for reply codec W4). Product hosts need a
fixed-depth pure encode for reply arms without waiting on general recursive
EDN ADT identity.

## Decision

1. Ship **`secret-reply-edn`** (wasm32, no `kotoba:typed`):
   - `secret_reply_value_edn(value)` → `{:tag :value :value "…"}`
   - `secret_reply_error_edn(code,message)` → `{:tag :error :code "…" :message "…"}`
   - Dual quote/backslash scan on string leaves (reject → empty)
   - Code is a plain string atom (not keyword) for pure codec
   - `main` → **-2302**
2. Package sha `5b7be773…`.

Honesty:

- Fixed-depth only; does **not** claim W4 recursive nested EDN ADT.
- Does **not** flip secret kit `:wasm-aot :implemented` (host fetch + full
  kit project body still open).
- Complements HTTP reject-path result arms (0217/0218) on the secret surface.

## Evidence

- KIR main → -2302; value/error ok + quote/empty-code reject
- ops kit registry + sha tests

## Related

- T8.3; ADR 0206, 0217–0218, 0231
- Follow-up: Component twin; W4; wasm-aot flip when production-admissible
