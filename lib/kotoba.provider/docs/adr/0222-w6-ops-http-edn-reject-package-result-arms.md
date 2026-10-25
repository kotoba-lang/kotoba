# ADR 0222: T8.3 result arms in http-edn-reject-package multi-export

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0221 multi-export kit body; kotoba-component result-arm package
  cases (`bee9c87a`)

## Context

ADR 0221 shipped multi-export reject kit body with headers empty + append +
request. Result arms remained single-export Components (0217–0218). Hosts
need result encode in the same shared-memory package for a complete reject-
path EDN surface without pre-validated atoms.

## Decision

1. **kotoba-component** extends `:http-edn-reject-package` with optional
   `:http-result-ok-edn` and `:http-result-err-edn` export cases (shared
   realloc / scan / write-u64).
2. Re-ship **`http-edn-reject-package`** with five exports: empty, append,
   request, result-ok, result-err.

Honesty:

- True set / W4 still open.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- kotoba-component ≥ `bee9c87a`
- Component digest `574dcb55…`; live wasmtime empty/request/ok/err/reject
- ops kit registry + sha tests

## Related

- T8.3; ADR 0217–0221
- Follow-up: true set / W4; `:wasm-aot :implemented`
