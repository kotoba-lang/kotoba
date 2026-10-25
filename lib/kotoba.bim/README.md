# kotoba-lang/bim

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-bim`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI BIM: an IFC-like model for building authoring. Spatial hierarchy
(Project -> Site -> Building -> Storey -> Space), element taxonomy
(Wall/Slab/Column/Beam/Door/Window/Roof/Stair/Railing/Furniture/
MepSegment/Opening), PropertySet (Pset_*) and Qto_* quantities (IFC
convention), material/layer/classification, and a link to
`kotoba-lang/brep` for element geometry (BREP body or Axis+Profile
sweep) plus a scene-projection format for storey-LOD rendering.

Depends on `kotoba-lang/brep` for element BREP geometry.

Drawing exchange uses shared DXF and ISO PDF libraries. JVM workflows that
require Autodesk DWG can use `bim.interchange.dwg/export-floor-plan!` with an
explicitly configured ODA/Autodesk-compatible DXF→DWG converter command. The
adapter verifies the converter exit status and recognized DWG `AC10xx` file
signature, so ASCII DXF content is never mislabeled as DWG.

## Status

Restored — the single-namespace data model ported from the original
465-line Rust `lib.rs`, with both original Rust unit tests mirrored 1:1
in `test/bim_test.cljk` (+1 smoke test) — 3 tests / 6 assertions, 0
failures. Pure data + pure functions throughout; no IO/GPU. The
original's serde-JSON round-trip test is adapted to a direct nested-
hierarchy construction check — EDN maps are already the data, no
serialize/deserialize step is needed to prove the model holds together.

## Develop

```bash
kbb -M:test
```
