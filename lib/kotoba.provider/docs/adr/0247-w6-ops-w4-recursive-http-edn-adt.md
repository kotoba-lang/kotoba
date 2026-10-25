# ADR 0247: T8.3 / W4 second ops slice — recursive HTTP request/result EDN ADT

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0246 recursive-headers-edn; W4 recursive tree values

## Context

ADR 0246 shipped the first ops residual beyond fixed-depth EDN: sealed
`:edn/node` atom|pair + recursive print for header lists. The residual gate
for full kit identity still needed **request** and **result** as recursive
EDN ADT surfaces (not only fixed-depth string-concat codecs).

## Decision

1. Ship **recursive-http-edn** (wasm32, kotoba:typed):
   - Same sealed `:edn/node` = `:atom string | :pair [node node]`
   - `headers_list_edn` (0246 surface)
   - `request_tree_edn` — right-nested pair spine of preformatted entry atoms
     → `{:url … :headers […] :body … :timeout-ms N}`
   - `result_ok_tree_edn` / `result_err_tree_edn` — same spine for ok/err arms
   - Entry atoms keep ADT depth under the closed schema limit (8); nested
     `pair(kv, …)` of variant pairs exceeded depth when keys/values were
     separate nodes
   - Dual quote/backslash reject; status ∈ [100,599]; empty/forbidden fail closed
   - main → **-2402**
2. Honesty: entry-atom spine + headers vector atom — **not** nested records
   inside recursive variants. Does **not** alone flip `:wasm-aot :implemented`
   (host I/O + nested-record-in-variant still open).
3. ABI max-arity 5: request takes prebuilt `headers-edn` string from
   `headers_list_edn` rather than inlining 4 header fields.

## Evidence

- Package sha `d2a07804…`; browser-host main → -2402
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0246; fixed-depth HTTP 0209–0242
