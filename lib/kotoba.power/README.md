# kotoba-lang/power

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-power`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Power: UPF power intent parsing, static/dynamic power estimation, IR
drop grid analysis, and electromigration rule checking.

| Namespace | Restored from | Purpose |
|---|---|---|
| `power.upf` | `upf` | Unified Power Format (UPF) text parser (domains/switches/isolation/retention/level-shifters) + validation |
| `power.estimation` | `estimation` | Static (leakage) + dynamic (switching) power formulas |
| `power.ir-drop` | `ir_drop` | Resistive power-grid IR drop analysis via Gauss-Seidel relaxation |
| `power.em` | `em` | Electromigration (EM) rule checking |

## Status

Restored — all 4 modules ported from the original 622-line Rust `lib.rs`,
with all 6 original Rust unit tests mirrored 1:1 in `test/power_test.cljk`
(+2 extra tests for full domain coverage) — 8 tests / 24 assertions, 0
failures. Pure data + pure functions/parsers throughout; no IO/GPU.
`power.ir-drop`'s Gauss-Seidel solve is coarse-grained per-analysis
(bounded 500-iteration relaxation on a small grid), not a per-frame hot
loop.

## Develop

```bash
kbb -M:test
```
