# ADR 0246: T8.3 / W4 first ops slice — recursive nested EDN ADT for headers

- Status: Accepted
- Date: 2026-08-01
- Depends: W4 recursive tree values (compiler recursive_tree_value_test);
  fixed-depth HTTP EDN packages through 0242

## Context

Ops kits completed pure **fixed-depth** EDN packages (string-concat codecs).
The residual gate for `:wasm-aot :implemented` is **W4 recursive nested EDN
ADT** for kit `:request`/`:result` identity — not more fixed-depth folds.
W4 document/tree values already land in the compiler; ops need the first
recursive EDN ADT surface.

## Decision

1. Ship **recursive-headers-edn** (wasm32, kotoba:typed):
   - Sealed recursive `:edn/node` = `:atom string | :pair [node node]`
   - `edn_atom` / `edn_pair` / `edn_print` (space-joined recursive walk)
   - `headers_list_edn` builds two header atoms + prints `[… …]`
   - Dual quote/backslash reject on name/value
   - main → **-2401**
2. Honesty: binary-tree spine of pre-formatted header map atoms — **not**
   yet full kit request/result recursive identity. Does **not** alone flip
   `:wasm-aot :implemented`.
3. Nested records inside recursive variants remain outside closed schema
   profile; atoms+pair spine is the admitted recursive shape.

## Evidence

- Package sha `7b074e20…`; KIR main → -2401
- ops kit registry + sha tests

## Related

- T8.3 residual W4; compiler W4 recursive tree; HTTP 0209–0242 fixed-depth EDN
