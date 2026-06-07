"""
MitateAllergyIgePanelOrderCell — IgE panel order routing to external clinical lab.

Per ADR-2605260115 §Decision 2 (View39-equivalent IgE panel) + ADR-2605260100 §Decision 3 G2 + G4 + G7.

Pregel graph (3 nodes):

    receive_triage_recommend    <-  upstream: mitate_rhinitis_triage or
                                    mitate_treatment_router (condition-1-rule-in indication)
        |
        v
    order_construct_g2_g4       ->  build diagnosticOrder lexicon record:
                                      orderType = "ige-panel-39"
                                      scopedAntigens = perennial set
                                      consentReceiptCid (G1)
                                      physicianAttestorDid (G4 R2+ required)
                                      resultDeliveryChannel = "encrypted-mst-envelope" (G2)
        |
        v
    route_to_external_lab       ->  XRPC: post to external lab DID registry
                                    (jurisdiction-aware, JP / EMA / FDA)
                                    cold-chain logistics scheduling (naphtali coordination)
                                    await diagnosticResult; on receipt, emit downstream
                                    (mitate_treatment_router or condition-1 specific path)

Tier: B (Per-Domain).
Murakumo node (proposed): naphtali.
Charter Rider §2 risk: §2(c) MEDIUM (external lab data path — G2 + G7 enforce zero-resale).
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# COUNCIL ACTIVATION GATE (R2 invariant — licensed MD-in-loop mandatory)
# ─────────────────────────────────────────────────────────────────────────────

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
SILEN_MITATE_BASELINE_REVIEW_CID: str | None = None
CONDITION_1_IGE_PANEL_ANTIGEN_LIST_BASELINE_CID: str | None = None
EXTERNAL_LAB_DID_REGISTRY_CID: str | None = None
ENCRYPTED_ENVELOPE_RECIPIENT_REGISTRY_CID: str | None = None
LICENSED_MD_REGISTRY_CID: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or SILEN_MITATE_BASELINE_REVIEW_CID is None
    or CONDITION_1_IGE_PANEL_ANTIGEN_LIST_BASELINE_CID is None
    or EXTERNAL_LAB_DID_REGISTRY_CID is None
    or ENCRYPTED_ENVELOPE_RECIPIENT_REGISTRY_CID is None
    or LICENSED_MD_REGISTRY_CID is None
):
    raise RuntimeError(
        "mitate_allergy_ige_panel_order cell scaffold-only — Council has not "
        "attested (a) master charter, (b) condition-1-ige-panel-antigen-list "
        "baseline, (c) external lab DID registry, (d) encrypted envelope "
        "recipient registry (G2 + G7), or (e) licensed MD registry (G4). "
        "Do not deploy."
    )
