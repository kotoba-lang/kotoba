# ADR 0216: T8.3 reject-path headers_edn_append Component

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0215 http_header_edn; kotoba-component `:headers-edn-append`

## Context

ADR 0214–0215 shipped reject-path `edn_quoted` and `http_header_edn`. The next
host-sequenced fold step in `http_request_edn` is `headers_edn_append(acc, name,
value)` — dual-scan header map, reject on existing `:name "…"` marker
(substring uniqueness, not a true set), splice into `[]` or existing vector.
Without this Canonical shape, multi-export request-edn reject composition
cannot close honestly.

## Decision

1. **kotoba-component** admits `:headers-edn-append` — Canonical
   `string × string × string → string` with dual UTF-8 quote/backslash scan,
   `:name "…"` substring uniqueness, and vector splice. WAT owns semantics.
2. Ship **`http-headers-edn-append`** (wasm32 + Component).

Honesty:

- Uniqueness is **substring scan**, not a true set (W4).
- Does **not** Component-re-emit `http_request_edn` / result arms.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- `kotoba compile --target component` with kotoba-component ≥ `db026a32`
- Component digest `c139ff32…`; live wasmtime empty-vec / second / dup / bad-atom
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0215; kotoba-component `:headers-edn-append`
- Follow-up: request/result reject-path composition; true set / W4; multi-file kit body
