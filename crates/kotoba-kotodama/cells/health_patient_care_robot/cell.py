"""
health_patient_care_robot — Robotics orchestration.

Pregel graph: receive_vitals_alert → dispatch_care_assist (recipe = fluid_intake + pose_adjust) → hc_telemetry → emit_patient_stabilized.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"health_patient_care_robot cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of levi not attested."
    )
