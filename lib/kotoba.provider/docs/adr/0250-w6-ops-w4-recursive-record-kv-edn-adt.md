# ADR 0250: T8.3 / W4 fifth ops slice — record-typed kv entries in recursive EDN

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0248–0249 true-kv pair spines; compiler ADR 0196; kir ADR 0025

## Context

ADR 0248/0249 honesty claimed **nested records inside recursive variants**
remain outside the closed schema profile (schema reject / infer crash on
`[:ref :record]`). Remeasured 2026-08-01 against current compiler:

- Closed schema admits `:edn/kv` record + recursive `:edn/node` with
  `:entry [:ref :edn/kv]` arm (productive constructor cycle rule).
- Construct (`variant-new` + `record-new`), match (`match-variant` +
  `record-get`), and recursive print all succeed on wasm32 typed host.
- 4-field request/result maps work under ADT depth 12.

So the residual was **stale documentation**, not a language ceiling. This
slice ships the first ops package that uses true record-typed map entries
instead of `pair(atom k, atom v)`.

## Decision

1. Ship **recursive-record-kv-edn** (wasm32, kotoba:typed):
   - Schemas: `:edn/kv` record `{k v}` + `:edn/node` =
     `:atom string | :entry kv | :pair [node node]`
   - `edn_entry` / `edn_print` (entry prints as `k v`)
   - `header_rec_kv_edn`, `headers_list_edn`
   - `request_rec_kv_edn` → `{:url :headers :body :timeout-ms}`
   - `result_ok_rec_kv_edn` / `result_err_rec_kv_edn` 4-field arms
   - main → **-2405**
2. Closes the **record-in-variant** residual for ops recursive EDN identity.
3. Does **not** alone flip `:wasm-aot :implemented` — **host I/O** remains.
4. Does not claim unbounded recursive Clojure-style maps; still bounded
   sealed ADT + depth budget.

## Evidence

- Package sha `dfd44b0c…`; browser-host main → -2405
- ops kit registry + sha tests
- Probe: schema validate + compile + runtime before package ship

## Related

- T8.3 residual W4; ADR 0246–0249; compiler closed schema (`schema.cljc`);
  document-in-record path that previously expanded closed primitives
