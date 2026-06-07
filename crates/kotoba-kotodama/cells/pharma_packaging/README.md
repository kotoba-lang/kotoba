# pharma_packaging — Pregel cell for secondary packaging + lot release

Per **ADR-2605250545 §Decision 4** (secondary packaging) +
**ADR-2605250500 §Decision 3 G11** (Wellbecoming label content).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **dan** (decommission leader — end-of-lot packaging is the
natural "lot 終端" pair to dan's existing end-of-life decommissioning role for kuni-umi).

Responsibilities:
- 厚紙箱 (FSC recycled cardboard) + 添付文書 (recycled paper, soy ink)
- Label scanner G11 enforcement (e.g. naphazoline ≥ 0.05% MUST carry 連用警告)
- Apache 2.0 + Charter Rider notice (ADR-2605192200 §3 attribution)
- Lot release attestation chain (final lotAttestation with all upstream CIDs)
- QP-equivalent DID + witness DID per lot (G4 + G9)
- Spent material / off-spec lot routing to disposal (category 7)
