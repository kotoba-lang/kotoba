# kotoba-lang/engineer

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-eng-core`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

Shared CAD/EDA engineering foundation. One namespace per original Rust `pub mod`:

| Namespace | Restored from | Purpose |
|---|---|---|
| `engineer.constraint` | `constraint` | Geometric + parametric constraint status solver |
| `engineer.parameter` | `parameter` | Named parameters with min/max bounds |
| `engineer.history` | `history` | Command-pattern undo/redo stack |
| `engineer.measurement` | `measurement` | Distance/angle measurement |
| `engineer.selection` | `selection` | Pick / box-select / chain-select sets |
| `engineer.layer` | `layer` | Layer visibility/lock/color manager |
| `engineer.grid` | `grid`/`snap` | Grid config + point-snap |
| `engineer.drc` | `drc` | Design Rule Check violation reporter |

Consumed by domain repos (dft/spice/pdk/pnr/bim/rtl/cad/cae-solver/eda) and
`kotoba-lang/{engineer-io,engineer-render}`.

## Status

Restored — all 8 modules ported from the original 726-line Rust `lib.rs`,
with all 7 original Rust unit tests mirrored 1:1 in `test/engineer_test.cljk`.
Pure data + pure functions throughout (no IO/GPU); the constraint solver is a
status *evaluator* against fixed point positions, matching the original
Rust's scope (it never implemented iterative Newton-Raphson point relaxation
either — `max-iterations`/`tolerance` are carried but unused pending a real
geometric solver, future work if a domain repo needs it).

## Develop

```bash
kbb -M:test
```
