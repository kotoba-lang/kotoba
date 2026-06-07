# igata_trim_machining — Pregel cell for sprue/runner trim + flash + CNC post-machining

Per **ADR-2605261200 §Design Pregel cells #6**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **simeon** (finishing specialist).

**G10 enforcement cell** — scrap recovery ≥95% tracked end-to-end here (sprue + runner + flash + CNC chip + scrap from reject branch in `igata_post_cast_qc`).

Open-source toolchain (G3):
- **CAM**: LinuxCNC + FreeCAD Path workbench (no proprietary `.iges`/`.x_t` lock-in)
- **G-code dialect**: standard RS-274 / LinuxCNC variant
- **Cutting tools**: industry-standard (carbide insert + open-spec geometry)
- **Coolant**: water-soluble emulsion (G7=NONE: no chlorinated additive, no PFAS)

Decision branch (`post_machining_decision`):
- **as-cast** path: HPDC near-net-shape; no machining required. Cast surface within tolerance (typical Al-Si HPDC = ±0.1 mm at die-finished surface).
- **cnc** path: datum-feature or critical interface surface (bolt seat, locating hole, sealing groove, mating flange). CNC adds ~10-30 sec per part for typical structural feature.

Scrap recovery (G10):
- Sprue + runner mass = typically 15-30% of total melt per shot (highly geometry-dependent)
- Flash mass = typically 1-3%
- Chip recovery from CNC = typically 5-15% of CNC-removed volume
- Reject parts from `igata_post_cast_qc` = remelted in next `igata_alloy_melt` cycle
- **All routes converge to next-cycle melt input via Otete handling + per-mass-flow logging**
