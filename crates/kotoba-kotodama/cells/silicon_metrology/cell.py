"""
SiliconMetrologyCell — overlay + CD-SEM + particle inspection orchestration.

Per ADR-2605242545 §Decision 1 row 6.

Reference vendor: KLA (1-company near-monopoly).

Pregel graph (4 nodes — adds AI inference step):
    receive_wafer_lot       <-  any process cell (litho/etch/depo/cmp/implant)
        |
        v
    dispatch_inspection     ->  XRPC: tsukuru.equipment.dispatch (recipe = scan area + resolution)
        |
        v
    classify_defects        ->  iwakura AgentChat call (BitNet ternary vision model)
                                — runs locally on simeon node (co-located with iwakura sim)
        |
        v
    emit_wafer_lot          ->  MST PUT waferLotAttestation
                                (process_history += defect_count + classification)
                            ->  feed-back to upstream cell if defects > threshold (reprocess)
                            ->  forward to silicon_test if defects acceptable

Tier: B. Murakumo node (proposed): simeon (iwakura sim co-location).
Charter Rider §2(a)(c): MEDIUM — CD-SEM inspection AI MUST NOT be retargeted
to human face / person identification (§2(c) violation).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None
SILEN_FORCE_AI_DATASET_ATTESTATION_CID: str | None = None

if (
    COUNCIL_FLEET_ATTESTATION_TX_HASH is None
    or SILEN_FORCE_AI_DATASET_ATTESTATION_CID is None
):
    raise RuntimeError(
        "silicon_metrology cell scaffold-only — Council `simeon` co-location "
        "attestation + AI training dataset attestation (wafer-defect ONLY, no "
        "human/face data) per ADR-2605242545 §5 + equipment/metrology/README.md "
        "§Charter Rider gate."
    )
