"""
hr_interview_kiosk_robot — Robotics orchestration.

Pregel graph: receive_candidate_arrival → dispatch_interview_terminal (recipe = voice_module + facial_track) → hr_telemetry → emit_interview_completed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"hr_interview_kiosk_robot cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of joseph not attested."
    )
