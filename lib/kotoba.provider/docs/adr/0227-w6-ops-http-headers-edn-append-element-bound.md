# ADR 0227: T8.3 map-element-bound name uniqueness on headers-edn-append

- Status: Accepted
- Date: 2026-08-01
- Depends: kotoba-component ≥ `7e017bbc` (`:headers-edn-append` / multi-export);
  ADR 0216, 0224–0226

## Context

ADR 0216 / multi-export reject package used free substring `:name "…"`
marker scan for header-**map** uniqueness. ADR 0225/0226 closed the
name-**list** plane with element-bound equality; Progress gj honesty still
called out map append as marker scan.

## Decision

1. **kotoba-component** upgrades Canonical `:headers-edn-append` (and the
   multi-export package append export) to **map-element-bound** membership:
   `{` preceded by `[` or space, then `{:name "…"}` field. Prefix non-collision
   (Host + Ho) is live.
2. Re-ship **`http-headers-edn-append-component`** (`ed8d6a1f…`) and
   **`http-edn-reject-package-component`** (`e1de58c7…`) against component
   `7e017bbc`.

Honesty:

- Bounded EDN map-vector dialect (not unbounded hash-set / W4 recursive ADT).
- Does **not** flip `:wasm-aot :implemented` (W4 recursive nested EDN open).
- Pure ADR 0224 set ADT path remains complementary for wasm32/typed hosts.

## Evidence

- kotoba-component#115 MERGED (`7e017bbc`): 54 tests / 620 assertions
- Component digests above; wasmtime live empty/second/dup/prefix
- ops kit registry + sha tests

## Related

- T8.3; ADR 0216, 0221–0226
- Follow-up: W4 recursive nested EDN; only then `:wasm-aot :implemented`
