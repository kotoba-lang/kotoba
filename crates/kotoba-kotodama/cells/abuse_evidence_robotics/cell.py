"""
abuse_evidence_robotics — Robotics orchestration.

Pregel graph: receive_violation_report → dispatch_evidence_collector (recipe = camera_angle + environmental_log) → abuse_telemetry → emit_evidence_secured.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"abuse_evidence_robotics cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of asher not attested."
    )
