# kotoba-lang/cnc-toolpath

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-cam`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI CAM: Computer-Aided Manufacturing — toolpath generation, G-code
output, tool library, and stock definition. Accepts geometry as
generic input (`[x y z]` points / mesh data) to avoid a circular
dependency on `kotoba-lang/brep` (the restored kami-cad).

**Named `cnc-toolpath`, not `cam`** — "cam" is dangerously ambiguous
(camera vs. Computer-Aided Manufacturing) in a large,
actively-developed org with real camera-rig work elsewhere, same class
of correction as `kami-si` -> `signal-integrity`.

| Namespace | Restored from | Purpose |
|---|---|---|
| `cnc-toolpath.tool` | `tool` | Cutting tool definitions + tool library |
| `cnc-toolpath.stock` | `stock` | Workpiece stock definitions + material presets |
| `cnc-toolpath.toolpath` | `toolpath` | CAM operations + toolpath segment generation (zigzag pocket, peck-drill) |
| `cnc-toolpath.gcode` | `gcode` | G-code generation with post-processor configuration |

## Status

Restored — all 4 modules ported from the original 973-line Rust source
(`lib.rs` + `tool.rs` + `stock.rs` + `toolpath.rs` + `gcode.rs`), with
all 5 original Rust unit tests mirrored 1:1 in
`test/cnc_toolpath_test.cljk` (+1 smoke test) — 6 tests / 56 assertions,
0 failures. Pure data + pure functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
