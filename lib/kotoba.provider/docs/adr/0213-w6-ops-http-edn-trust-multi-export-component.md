# ADR 0213: T8.3 multi-export EDN trust package Component

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0212 single-export string-expression twins; kotoba-component#102
  `:string-expression-package`

## Context

ADR 0212 shipped two single-export Component twins (`headers-edn-empty`,
`http-header-edn-trust`) because kotoba-component only admitted one
string-expression export per core module. Full multi-export `http-request-edn`
(reject path with conditionals, uniqueness scan, i64 fields) still has no
qualified Canonical lowering. Trust-path pure `string-concat` arms can share
one package once multi-export admission exists.

## Decision

1. **kotoba-component#102** admits `:string-expression-package` — N pure
   string-concat exports sharing memory/realloc/data.
2. Ship **`http-edn-trust-package`** (wasm32 + Component) with six exports:
   - `headers-edn-empty`, `http-header-edn-trust`, `headers-edn-one`
   - `http-request-edn-trust` (timeout pre-rendered as decimal string by host)
   - `http-result-ok-edn-trust`, `http-result-err-edn-trust` (status/retryable
     pre-rendered by host)

Honesty:

- Host pre-validates atoms (no quote/backslash) and formats i64 fields.
- Rejecting encoder remains `http-request-edn` (ADR 0209–0211).
- Does **not** Component-re-emit uniqueness scan / conditionals / true set.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- `kotoba compile --target component` with kotoba-component ≥ `90b5c8b3`
- Component digest `f2ea2037…`; live wasmtime invokes for all 6 exports
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0212; kotoba-component#102
- Follow-up: reject-path Component shape (if/let/substring composition);
  true set / W4 recursive ADT; multi-file kit body
