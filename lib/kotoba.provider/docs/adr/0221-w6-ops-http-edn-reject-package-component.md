# ADR 0221: T8.3 multi-export http-edn-reject-package Component kit body

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0216–0220 single-export reject surfaces; kotoba-component
  `:http-edn-reject-package`

## Context

Single-export reject-path Components cover empty headers, append, request,
and result arms. Trust path already has multi-export
`:string-expression-package` (ADR 0213). Reject path still needed a shared-
memory multi-export kit body for host-sequenced fold composition without
pre-validated atoms.

## Decision

1. **kotoba-component** admits `:http-edn-reject-package` — multi-export
   package requiring headers empty + append + request-edn (or edn0), optional
   additional reject roles; shared realloc / scan / uniqueness / decimal.
2. Ship **`http-edn-reject-package`** (wasm32 + Component) with three exports:
   `headers-edn-empty`, `headers-edn-append`, `http-request-edn`.

Honesty:

- Uniqueness remains substring scan (not true set / W4).
- Does **not** flip `:wasm-aot` to `:implemented` (true set / full multi-file
  kit + result arms in same package still open).
- Existing single-export reject twins remain valid.

## Evidence

- kotoba-component ≥ `93e1c7a4`
- Component digest `21f7a192…`; live wasmtime empty/append/request ok/reject
- ops kit registry + sha tests

## Related

- T8.3; ADR 0213–0220; kotoba-component `:http-edn-reject-package`
- Follow-up: result arms in package; true set / W4; `:wasm-aot :implemented`
