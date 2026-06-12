"""
SiliconDepositionCell — CVD/PVD/ALD 成膜 orchestration.

Per ADR-2605242545 §Decision 1 row 2 + §Decision 2.

Reference vendors: AMAT / Lam / TEL.

Pregel graph (3 nodes):
    receive_wafer_lot   <-  predecessor (silicon_etch / silicon_cmp / new lot)
        |
        v
    dispatch_deposition ->  XRPC: tsukuru.equipment.dispatch
                            (recipe = precursor / temp / pressure / pulse-seq)
        |
        v
    emit_wafer_lot      ->  MST PUT waferLotAttestation
                        ->  silicon_metrology (thickness QC)

Tier: B. Murakumo node (proposed): judah.
Charter Rider §2(a)(c): MEDIUM (precursor chemistry may overlap with CW).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None
SILEN_FORCE_BASELINE_REVIEW_CID: str | None = None

if (
    COUNCIL_FLEET_ATTESTATION_TX_HASH is None
    or SILEN_FORCE_BASELINE_REVIEW_CID is None
):
    raise RuntimeError(
        "silicon_deposition cell scaffold-only — Council fleet.toml addition "
        "of `judah` not attested, or silen-force baseline review missing. "
        "Per ADR-2605242545 §Decision 5 + ADR-2605242500 §Decision 4."
    )
