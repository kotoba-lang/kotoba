# ADR 0233: T8.3 full headers EDN via typed-set-nth fold

- Status: Accepted
- Date: 2026-08-01
- Depends: compiler ADR 0194; kotoba-kir ADR 0024; provider ADR 0231

## Context

ADR 0231 held kit-shaped set-of-header-records but EDN encode only emitted
headers-n (no set iterator). Compiler/kir/wasm landed typed-set-nth for guest
fold over sorted set items.

## Decision

1. Ship **http-headers-edn-set-fold** (wasm32, kotoba:typed):
   - set-of-header-records + parallel name-set uniqueness
   - **http_hdr_edn** folds via typed-set-nth into full EDN vector of
     `{:name … :value …}` maps
   - main → **-9002**
2. Does not flip wasm-aot (W4 recursive nested EDN still open).

## Evidence

- Package sha `530f9936…`; KIR main → -9002
- 85 tests / 816 assertions green

## Related

- T8.3; ADR 0231, compiler 0194, kir 0024
