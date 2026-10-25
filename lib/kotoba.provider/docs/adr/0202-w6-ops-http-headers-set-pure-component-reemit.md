# ADR 0202: T8.3 pure Component re-emit of typed headers-set packing walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0189 typed-string headers-set packing; kotoba-component#97
  (`:http-headers-set-package-with-main`); ADR 0200–0201 header name/value

## Context

ADR 0189 shipped a typed-host wasm module for host-sequenced header set
packing (`begin` / `pair` / `end` + live `main`). Pure Component packaging
needed Canonical multi-export with **nested** main composition (not flat
lit-only policy calls).

## Decision

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `http_headers_set_ok.kotoba` | `:http-headers-set-ok` | `:http-headers-set-ok-component` | **-3647** |

Policy (Canonical WAT):

- **begin(n)**: `-4` if `n∉[0,32]`; else remaining = n
- **pair(state,name,value)**: sticky err; `-8` if remaining=0; name tchar + value CTL; else remaining−1
- **end(state)**: sticky err; `-7` incomplete; `0` ok
- **main**: nested begin/pair/end composition with string/i64 lits

### Honesty

- Does **not** flip `:wasm-aot :implemented`
- Does **not** check header name uniqueness (W4 set storage)
- Does **not** pack nested request/result EDN

## Evidence

- digest match; wasmtime `main()` → `-3647`
- begin 0→0 / 40→−4; pair bad-name → −3
- ops-kit component twin registration

## Related

- T8.3; ADR 0187–0189, 0200–0201; kotoba-component#97
