# ADR 0236: T8.3 fixed-depth secret get-request EDN encode

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0232 secret reply EDN; secret_name_ok (0206)

## Context

Secret kit `:request` is `[:record [[:name :string]]]`. Reply arms landed in
ADR 0232; request encode was still host-only.

## Decision

1. Ship **secret-request-edn** (wasm32): `secret_request_edn(name)` →
   `{:name "…"}` with dual quote/backslash scan, empty reject, len ≤128.
2. `main` → **-2306**. Package sha `fde508bf…`.

Honesty: fixed-depth only; not W4. Does not flip secret wasm-aot.

## Evidence

- KIR main → -2306; ok/empty/quote reject
- ops kit registry + sha tests

## Related

- T8.3; ADR 0232, 0237 multi-export package
