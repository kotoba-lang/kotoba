"""
SeigyoScadaGatewayCell — L2 SCADA config-as-record + alarm ingestion.

Per ADR-2606111000 §1 (L2 row) + §6 row 3.

Pregel graph: receive_scada_project (FUXA | Rapid SCADA | OpenSCADA
project file) → charter_rider_audit → attest_project_cid
(seigyo.scadaProjectAttestation) → deploy_to_site → ingest_alarms
(full-fidelity seigyo.alarmEventRecord northbound — alarms are
operational facts, not personal telemetry per §5).

Vendor prohibition (§2): no proprietary SCADA/HMI runtime (AVEVA /
iFIX / Ignition / WinCC etc.); open-source per-site choice with
Charter Rider §2 audit each.

Tier: B. Murakumo node (proposed): judah.
Charter Rider §2(a)(c): MEDIUM (supervisory visibility; no direct actuation).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None
SILEN_SEIGYO_BASELINE_REVIEW_CID: str | None = None

if (
    COUNCIL_FLEET_ATTESTATION_TX_HASH is None
    or SILEN_SEIGYO_BASELINE_REVIEW_CID is None
):
    raise RuntimeError(
        "seigyo_scada_gateway cell scaffold-only — Council fleet.toml + "
        "silen-seigyo baseline not attested per ADR-2606111000 §6 + §8 R0."
    )
