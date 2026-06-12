# igata_post_cast_qc — Pregel cell for dimensional + X-ray CT + mechanical QC

Per **ADR-2605261200 §Design Pregel cells #5**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **levi** (verification + attestation specialist; same as `igata_part_attestation`).

QC suite (R1+ activated; R0 scaffold):

| Test | Standard | R-phase | Witness |
|---|---|---|---|
| Dimensional 3D scan vs. CAD | ISO 10360 + die-design tolerance | R1+ | Mimi |
| 2D radiograph porosity screen | ASTM E155 (reference plates) | R1+ | Mimi |
| X-ray CT porosity volumetric | ASTM E1441 + ASTM E1570 | R2+ | Mimi + 放射線取扱主任者 |
| Tensile (yield, UTS, elongation) | ASTM B557 / E8 (companion bar) | R1+ | per-shot or per-N |
| Surface defect classification (cold shut, flow line, gas blister, crack) | open visual classifier | R1+ | Mimi vision arm |

Reject branch:
- Routes to **scrap recovery cell** (G10 ≥95% scrap recovery invariant) — sprue + runner + reject part all remelted in next `igata_alloy_melt` cycle.
- `qcAttestation.verdict = "reject"` + reject-reason CID logged per G14.

R2+ X-ray CT requirement triggers **放射線取扱主任者** SME activation gate (parallel to yakushi 危険物取扱主任者 / dangerous-goods officer pattern).
