# ADR 0205: T8.3 HTTP packing walk surface complete; nested EDN residual (W4)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0199–0204 pure Component re-emits; packing walks 0185–0193;
  kit-readiness inventory honesty

## Context

T8.3 HTTP ops progressed from hand WAT Components through compiler-AOT
bounds/walks/typed-string packages to **pure Canonical Component re-emits**
of every policy package and host-sequenced packing walk:

| slice | ADRs | live main vectors |
|---|---|---|
| url / request_ok / response / error | 0199 | -130 / -13406 / -1012 / -13501 |
| header name / value+pair / set pack | 0200–0202 | -130 / -3036 / -3647 |
| request packing walk | 0203 | -13467 |
| result packing walk | 0204 | -12061 |

kit `:request` / `:result` still declare nested records and header **sets**.
Packing walks validate fields without producing a single nested EDN value.
A true EDN codec for those shapes needs recursive values (W4) or a handle/
flat-node model that is **not** the application programming model
(migration plan W4: handles are not the app API).

## Decision

1. **Declare the packing-walk Component surface complete** for T8.3 HTTP
   policy. kit-readiness evidence lists 0199–0204 Component twins.
2. **Keep `:wasm-aot :partial`** — do **not** flip to `:implemented` until
   nested EDN codec for kit `:request`/`:result` is admissible under W4.
3. Residual wording is explicit: nested EDN / full multi-file kit body is
   **W4-gated**, not another multi-export package missing from the registry.

### Honesty

- Does **not** claim production full kit body AOT
- Does **not** invent recursive EDN encode/decode under current value model
- Does **not** start live SCRAM/PG (T8.4 qualification path)

## Evidence

- Registry twins for 0199–0204 Components; wasmtime live mains listed above
- kit-readiness summary + http kit note updated this ADR
- Frontier Progress residual points at W4 nested EDN, not missing packages

## Related

- T8.3; ADR 0199–0204; frontier ADR-2607299400 Progress 31df/31dg
- W4 recursive values (migration plan); T8.4 live SCRAM/PG qualification
