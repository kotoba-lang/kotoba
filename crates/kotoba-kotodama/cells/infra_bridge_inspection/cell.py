"""
infra_bridge_inspection — Robotics orchestration.

Pregel graph: receive_inspection_order → dispatch_crawler (recipe = crack_detection + vibration_sensor) → infra_telemetry → emit_audit_report.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"infra_bridge_inspection cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of reuben not attested."
    )
