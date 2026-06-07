# mitate_nasal_smear_eosinophil — Pregel cell for 鼻汁好酸球 microscopy

Per **ADR-2605260115 §Decision 3** (condition 1 vs 2 differential) +
**ADR-2605260130** (condition 2 exclusion logic — eosinophil < 5%).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **zebulun** (analytical chemistry / wet workflow leader).

Robotics class: **Mimi pharma-analytical** (yakushi sibling reuse) for顕微鏡 + 自動 image acquisition.
Image classifier: Murakumo only (G12), gemma4:e4b vision distill medical variant (open weights, G13).

Output:
- 好酸球 % (≥20% → 条件 1 強支持 / <5% → 条件 2 支持 / 5-20% → 中間)
- NARES (Non-Allergic Rhinitis with Eosinophilia Syndrome) flag (好酸球 ≥20% + IgE 陰性) — Wave 2+ carve-out
