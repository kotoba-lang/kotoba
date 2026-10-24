# kotoba-lang/mine-pds

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-mine-pds`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Mine PDS: mining domain PDS primitives — mine registry, mineral
catalog, extraction history ledger.

## Status

Restored — the single-namespace ledger ported from the original 221-line
Rust `lib.rs`, with both original Rust unit tests mirrored 1:1 in
`test/mine_pds_test.cljk` (+1 smoke test) — 3 tests / 8 assertions, 0
failures. Pure data + pure functions throughout; no IO/GPU.
Mutation-returning operations return `[:ok ledger']` / `[:error kind
ledger]` (ledger unchanged) rather than Rust's `Result<(),
MinePdsError>`.

Note: `kotoba-lang/mine-ai` depends on this repo for `Mine`/`MineStatus`/
`ExtractionRecord` types.

## Develop

```bash
kbb -M:test
```
