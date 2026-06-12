"""
MitateParanasalCtRouteCell — 副鼻腔 CT 外部 imaging facility routing + DICOM 受領.

Per ADR-2605260145 §Decision 3.

Pregel graph (3 nodes):

    receive_ct_indication       <-  upstream: mitate_rhinitis_triage (condition 3
                                    rule-in or subtype refinement)
        |
        v
    construct_imaging_order     ->  diagnosticOrder:
                                      orderType = "paranasal-ct"
                                      consentReceiptCid (G1)
                                      physicianAttestorDid (G4 R2+)
                                      external imaging facility DID
                                      resultDeliveryChannel = "encrypted-mst-envelope-dicom" (G2)
        |
        v
    receive_dicom_and_score     ->  external facility uploads DICOM
                                    → G2 envelope wrap
                                    → licensed MD Lund-Mackay scoring (0-24)
                                    emit diagnosticResult; downstream:
                                      - treatment_router (CRSsNP / CRSwNP / 好酸球性 / 歯性 / 真菌性)
                                      - or ess_surgery_planner R3

Tier: B (Per-Domain). Murakumo node: simeon.
Charter Rider §2 risk: §2(c) HIGH (medical imaging — G2 envelope mandatory) + §2(f) MEDIUM
(radiation dose — protocol must follow ALARA, especially pediatric escalate-only).
"""

from __future__ import annotations

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
SILEN_MITATE_BASELINE_REVIEW_CID: str | None = None
CONDITION_3_CT_ROUTING_ENCRYPTION_BASELINE_CID: str | None = None
EXTERNAL_IMAGING_FACILITY_DID_REGISTRY_CID: str | None = None
DICOM_ENCRYPTION_ENVELOPE_BASELINE_CID: str | None = None
LUND_MACKAY_SCORING_PROTOCOL_CID: str | None = None
LICENSED_MD_REGISTRY_CID: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or SILEN_MITATE_BASELINE_REVIEW_CID is None
    or CONDITION_3_CT_ROUTING_ENCRYPTION_BASELINE_CID is None
    or EXTERNAL_IMAGING_FACILITY_DID_REGISTRY_CID is None
    or DICOM_ENCRYPTION_ENVELOPE_BASELINE_CID is None
    or LUND_MACKAY_SCORING_PROTOCOL_CID is None
    or LICENSED_MD_REGISTRY_CID is None
):
    raise RuntimeError(
        "mitate_paranasal_ct_route cell scaffold-only — Council has not attested "
        "R2 deploy prerequisites. Do not deploy."
    )
