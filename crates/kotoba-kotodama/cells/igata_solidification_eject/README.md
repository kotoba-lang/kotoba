# igata_solidification_eject — Pregel cell for dwell + ejection + cooling path

Per **ADR-2605261200 §Design Pregel cells #4**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **joseph** (same as `igata_shot_injection` — same physical HPDC machine).

Dwell time scaling (Al-Si, ≤5 kg parts, single-cavity die):
- Thin-wall (3-5 mm): ~3-5 sec
- Medium-wall (5-10 mm): ~5-8 sec
- Thick-wall (10-20 mm): ~8-15 sec
- > 20 mm wall: requires die thermal management redesign or PoreFree-equivalent technique

Cooling path branches:
- **HT-free recipe** (default for ≤5 kg parts; open-recipe equivalent to Tesla AS3) — natural air cool, no quench. Mechanical properties from rapid in-die solidification + Sr modification.
- **T6 recipe** (R2+; certain structural parts) — defer to `igata_heat_treatment` cell; ejected part transported to HT station.
- **Water spray** (only when geometry mandates; logs residual stress + distortion risk per G14).

Otete thermal armor requirement: part surface 400-500°C at ejection; Otete arm with thermal-resistant gripper + automated cool-down sequence. Direct human handling prohibited (G11 safety invariant).
