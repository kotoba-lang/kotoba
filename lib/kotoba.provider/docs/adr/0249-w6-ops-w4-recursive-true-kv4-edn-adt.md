# ADR 0249: T8.3 / W4 fourth ops slice — 4-field true-kv maps (depth 12)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0248 true-kv ≤3; compiler ADR 0196; kotoba-kir ADR 0025

## Context

ADR 0248 proved true nested `pair(key-atom, value-atom)` maps but stopped at
**3 fields** because `parametric-adt-depth` was 8. Compiler ADR 0196 + kir
ADR 0025 raised the limit to **12**, unlocking full kit request/result field
sets under true-kv structure.

## Decision

1. Ship **recursive-kv4-edn** (wasm32, kotoba:typed), compiler ≥ `9da7a60`:
   - Same sealed `:edn/node` atom|pair
   - `request_kv4_edn` → `{:url :headers :body :timeout-ms}`
   - `result_ok_kv4_edn` → `{:tag :ok :status :headers :body}`
   - `result_err_kv4_edn` → `{:tag :error :code :message :retryable}`
   - main → **-2404**
2. Honesty: still atom|pair true-kv, **not** nested records inside recursive
   variants (closed schema rejects). Does **not** alone flip
   `:wasm-aot :implemented` (host I/O + record-in-variant remain).
3. Build requires kir `adt-depth-limit` 12 + compiler artifact limits 12.

## Evidence

- Package sha `8e69b086…`; browser-host main → -2404
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0246–0248; compiler 0196; kir 0025
