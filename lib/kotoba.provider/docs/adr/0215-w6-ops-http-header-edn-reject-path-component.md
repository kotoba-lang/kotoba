# ADR 0215: T8.3 reject-path http_header_edn Component composition

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0214 edn_quoted Component; kotoba-component `:http-header-edn`

## Context

ADR 0214 shipped single-export `edn_quoted` (string → string reject-on-quote/
backslash). The next composition step in `http_request_edn` is
`http_header_edn(name, value)` — dual quote of name/value then
`{:name "…" :value "…"}`. Trust-path twins (0212–0213) pre-validate atoms and
do not reject. Without a dual-scan Canonical shape, multi-export request-edn
reject composition cannot close honestly.

## Decision

1. **kotoba-component** admits `:http-header-edn` — Canonical
   `string × string → string` that loop-scans both UTF-8 args for `0x22` /
   `0x5c`, returns empty on hit, else builds the header map. Admission matches
   `header_edn`-named bodies (not `trust`); WAT owns dual scan.
2. Ship **`http-header-edn`** (wasm32 + Component) as the reject-path
   composition slice on top of edn_quoted.

Honesty:

- Does **not** Component-re-emit multi-export
  `headers_edn_append` / uniqueness / `http_request_edn` / result arms.
- Does **not** flip `:wasm-aot` to `:implemented`.
- Does **not** claim W4 set uniqueness.

## Evidence

- `kotoba compile --target component` with kotoba-component ≥ `ce4a15c5`
- Component digest `c386f6cb…`; live wasmtime ok/reject cases
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0214; kotoba-component `:http-header-edn`
- Follow-up: multi-export append/uniqueness/result on top of header_edn;
  true set / W4; multi-file kit body
