# ADR 0201: T8.3 pure Component re-emit of typed header value/pair package

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0188 typed-string header value/pair; kotoba-component#96
  (`:http-header-value-package-with-main`); ADR 0200 header_name_ok Component

## Context

ADR 0188 shipped a typed-host wasm module for `http_header_value_ok` +
`http_header_pair_ok` + live `main`. Pure Component packaging was blocked
until kotoba-component admitted CTL-scan value policy and pair compose under
Canonical ABI (no `kotoba:typed`).

## Decision

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `http_header_value_ok.kotoba` | `:http-header-value-ok` | `:http-header-value-ok-component` | **-3036** |

| artifact | role |
|---|---|
| `http-header-value-ok-v1.component.wasm` | `kotoba compile --target component` |
| provenance | `:builder :kotoba-compiler/v1`, target `:wasm-component-kotoba-v1` |
| registry | `:artifact-kind :wasm-component`, `:component-lowering :kotoba-component/canonical` |

Policy (WAT Canonical):

- **value**: empty ok; `>8192` → `-2`; CTL `NUL/CR/LF` → `-3`
- **pair**: name tchar/len (`-1/-2/-3`); value `-2→-5`, `-3→-6`

### Honesty

- Does **not** flip `:wasm-aot :implemented`
- Does **not** pack header set uniqueness (W4) or nested EDN result
- Typed-host module remains for browser-host consumers

## Evidence

- digest match; wasmtime `main()` → `-3036`
- pair bad-name → `-3`; value ok → `0`
- ops-kit tests register component twin

## Related

- T8.3; ADR 0187–0189, 0200; kotoba-component#96
