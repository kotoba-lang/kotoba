# ADR 0118: T8.3 secret-request-edn Canonical Component lowering

- Status: Accepted
- Date: 2026-08-01
- Depends: provider ADR 0236 pure secret_request_edn; http-header-edn Component

## Context

Provider shipped pure wasm32 `secret_request_edn` (ADR 0236). Component
`--target component` failed with no qualified Canonical lowering. HTTP
header-edn already has a dual-scan map emitter; secret request is the
single-field twin (`{:name "…"}`) plus empty + len≤128 gates.

## Decision

1. Admit `:secret-request-edn` — Canonical `string → string`.
2. WAT owns dual quote/backslash scan, empty reject, length >128 reject,
   and `{:name \"…\"}` concat. No `kotoba:typed`.
3. Single export only (live main with string-length or remains wasm32 path).

## Evidence

- assert-supported → `:secret-request-edn`
- wasmtime live ok/empty/quote/long vectors

## Related

- T8.3; provider ADR 0236/0237; W4 residual remains
