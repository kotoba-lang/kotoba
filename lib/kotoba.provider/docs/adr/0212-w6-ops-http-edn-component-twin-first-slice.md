# ADR 0212: T8.3 Component twin first slice for nested EDN encode

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0209–0211 nested EDN encode family; kotoba-component
  `:string-expression` Canonical lowering

## Context

Full multi-export `http-request-edn` Component compile fails admission:
recursive helpers / conditionals have no qualified Canonical lowering and
main-only modules still import `kotoba:typed::literal` under generic scalar
emission. Existing `:string-expression` shape admits pure nested
`string-concat` of parameters and literals (or a lone literal) without
`kotoba:typed`.

## Decision

Ship **two** single-export packages (wasm32 + Component each):

| Package | Body | Component lowering |
|---------|------|--------------------|
| `http-headers-edn-empty` | literal `"[]"` | `:string-expression` |
| `http-header-edn-trust` | nested concat `{:name "…" :value "…"}` | `:string-expression` |

Honesty:

- Trust path for header concat — host pre-validates atoms (no quote/backslash).
  Rejecting encoder remains `http-request-edn` (ADR 0209+).
- Does **not** Component-re-emit multi-export request/result/uniqueness suite.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- `compile-component` succeeds; sha-registered packages; ops kit tests green
- digests: empty Component `6254c105…`, trust Component `d07a2c08…`

## Related

- T8.3; ADR 0209–0211; kotoba-component string-expression-wat
- Follow-up: multi-export request-edn package shape; true set uniqueness; W4
