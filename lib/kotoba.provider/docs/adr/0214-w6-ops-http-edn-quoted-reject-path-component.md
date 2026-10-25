# ADR 0214: T8.3 reject-path edn_quoted Component first slice

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0209 nested EDN encode; ADR 0212–0213 trust-path twins;
  kotoba-component#103 `:edn-quoted`

## Context

Trust-path packages (0212–0213) assume host-validated atoms. The reject-path
`edn_quoted` in `http_request_edn` scans for quote/backslash via recursive
helpers that have no qualified Canonical lowering. Without a scan shape,
multi-export request-edn Component cannot close honestly.

## Decision

1. **kotoba-component#103** admits `:edn-quoted` — Canonical `string → string`
   that loop-scans UTF-8 for `0x22` / `0x5c`, returns empty on hit, else wraps
   with quotes. Admission matches `edn_quoted`-named bodies; WAT owns scan.
2. Ship **`http-edn-quoted`** (wasm32 + Component) as the reject-path first
   slice.

Honesty:

- Does **not** Component-re-emit full multi-export `http-request-edn`
  (header/append/uniqueness/result + private helpers).
- Does **not** flip `:wasm-aot` to `:implemented`.
- Does **not** claim W4 set uniqueness.

## Evidence

- `kotoba compile --target component` with kotoba-component ≥ `026ed2f8`
- Component digest `6471d3de…`; live wasmtime ok/reject cases
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0213; kotoba-component#103
- Follow-up: header/request/result reject-path composition on top of edn_quoted;
  true set / W4; multi-file kit body
