# kotoba-lang/mine-ai

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-mine-ai`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Mine AI: AI-side heuristics for mining operations — deterministic,
explainable helpers for extraction risk scoring and next-period
extraction planning.

Depends on `kotoba-lang/mine-pds` for `mine`/`mine-status`/
`extraction-record` data shapes (duck-typed, not a hard code dependency).

## Status

Restored — the single-namespace risk-scoring/planning logic ported from
the original 165-line Rust `lib.rs`, with both original Rust unit tests
mirrored 1:1 in `test/mine_ai_test.cljk` (+1 smoke test) — 3 tests / 5
assertions, 0 failures. Pure data + pure functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
