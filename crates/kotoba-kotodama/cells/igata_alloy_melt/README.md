# igata_alloy_melt — Pregel cell for Al-Si alloy melt + holding + degassing

Per **ADR-2605261200 §Design Pregel cells #1**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **naphtali** (melt + raw material specialist).

Process reference (open-source, no proprietary "Tesla AS3"-style closed recipes):

- **AlSi9Mg0.3** (HT-free baseline open recipe) — Al + Si 9% + Mg 0.3% + Mn 0.4% + Fe 0.7% + trace Sr 0.02% + Ti 0.15%
- **AlSi7Mg0.3** (A356 equivalent open recipe; T6-treatable) — Al + Si 7% + Mg 0.3% + Mn ≤0.5% + Fe ≤0.5% + Sr modified
- **AlSi12** (eutectic; thin-wall casting) — Al + Si 12% + Mg ≤0.1% + Fe ≤0.7%

Hazard awareness:
- Melt temp 700-750°C (G9: induction + electric resistance only; no fossil-fired furnace)
- Rotary degasser H₂ purge (N₂ or Ar gas; cylinder handling per 高圧ガス保安法 + G11)
- Sr modifier: requires 危険物取扱主任者-equivalent operator (G11)
- G7=NONE: alloy composition baseline excludes OPCW Schedule + RoHS + radioactive (yakushi Wave 1c parity)
