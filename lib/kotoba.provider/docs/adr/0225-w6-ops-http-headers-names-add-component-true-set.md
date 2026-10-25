# ADR 0225: T8.3 Component twin — true-set header name list append

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0223 name-set wasm32; ADR 0224 pure EDN-append-set;
  kotoba-component `:headers-names-add` (`dfba9407`)

## Context

ADR 0223 ships wasm32 true-set uniqueness via `[:set :string]` guest records
(`kotoba:typed`). ADR 0224 wires that set ADT into pure multi-header EDN
append. Reject-path **Components** still used substring `:name "…"` scan
(ADR 0216 headers-edn-append / multi-export reject package). Progress gh
listed **Component twin of set uniqueness** as the next residual.

## Decision

1. **kotoba-component** admits Canonical lowering `:headers-names-add`
   (`string×string → string`): acc is EDN vector of quoted names
   (`[]` / `["Host" "Accept"]`). Membership is **element-bound exact
   equality** (open quote preceded by `[`/space; close quote followed by
   space/`]`) — not substring marker scan, no `kotoba:typed`.
2. Ship **`http-headers-names-add-component`** via
   `kotoba compile --target component` on admission skeleton source.
3. Live vectors: empty→one, second distinct, duplicate reject `""`, prefix
   non-collision (`Host` + `Ho`), bad atom reject.

Honesty:

- Bounded EDN string-vector dialect (not unbounded hash-set / W4 recursive ADT).
- Does **not** replace headers-edn-append map EDN path (still substring there).
- Does **not** fold into multi-export reject package yet.
- Does **not** flip `:wasm-aot` to `:implemented`.

## Evidence

- kotoba-component ≥ `dfba9407` (`headers-names-add-canonical-lowering` 14 assertions)
- Package sha `939b4bfd…`; wasmtime live vectors as above
- Registry + digest tests

## Related

- T8.3; ADR 0216, 0221–0224; Frontier Progress residual Component twin
- Follow-up: fold names-add into multi-export reject package; W4 recursive EDN;
  only then `:wasm-aot :implemented`
