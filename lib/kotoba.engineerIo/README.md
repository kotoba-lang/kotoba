# kotoba-lang/engineer-io

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-eng-io`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

CAD/EDA file-format I/O. One namespace per original Rust `pub mod`, plus a
top-level FileFormat registry:

| Namespace | Restored from | Purpose |
|---|---|---|
| `engineer-io.format` | `FileFormat` enum | Format keywords + extension/mime-type/detection (20 CAD/EDA/RTL/CAM formats) |
| `engineer-io.stl` | `stl` | STL ASCII + binary exporter |
| `engineer-io.gerber` | `gerber` | Gerber RS-274X generator |
| `engineer-io.step` | `step` | STEP AP214 header/footer generator |

Depends on `kotoba-lang/engineer` for shared contracts (constraint/DRC/etc).

## Status

Restored — all 4 modules ported from the original 314-line Rust `lib.rs`,
with all 4 original Rust unit tests mirrored 1:1 in
`test/engineer_io_test.cljk`. `stl/export-binary` is JVM-only
(`#?(:clj ...)`, uses `java.nio.ByteBuffer`); a CLJS arm can be added if a
browser consumer needs binary STL export.

## Develop

```bash
kbb -M:test
```
