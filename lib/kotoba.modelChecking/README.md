# kotoba-lang/model-checking

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-verify`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Verify: formal verification (equivalence checking, model checking,
SVA assertions) and coverage analysis for digital designs.

**Named `model-checking`, not `verify`** — `verify` is a generic verb
with high future collision risk in a large, actively-developed org, same
class of correction as `kami-si` -> `signal-integrity`.

| Namespace | Restored from | Purpose |
|---|---|---|
| `model-checking.equivalence` | `equivalence` | Exhaustive combinational equivalence checking (< 20 inputs) |
| `model-checking.model-check` | `model_check` | BFS-based bounded model checking (safety/liveness/reachability) |
| `model-checking.assertion` | `assertion` | SVA-style assertion evaluation over signal traces |
| `model-checking.coverage` | `coverage` | Coverage collection/reporting (line/toggle/branch/condition/FSM/functional) with cross-bin support |

## Status

Restored — all 4 modules ported from the original 753-line Rust `lib.rs`,
with all 6 original Rust unit tests mirrored 1:1 in
`test/model_checking_test.cljk` (+2 extra tests for full domain coverage)
— 8 tests / 23 assertions, 0 failures. Pure data + pure functions
throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
