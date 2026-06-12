"""
health_safety_sanitization_bot — Robotics orchestration.

Pregel graph: receive_hazard_alert → dispatch_uvc_robot (recipe = uv_dose + path_coverage) → hs_telemetry → emit_area_sanitized.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"health_safety_sanitization_bot cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of levi not attested."
    )
