"""
marine_insurance_survey_robot — Hybrid Robotics orchestration.

Pregel graph: receive_claim_area → dispatch_damage_uav (recipe = visual_inspect + thickness_gauge) → survey_telemetry → emit_survey_report_signed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"marine_insurance_survey_robot cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
