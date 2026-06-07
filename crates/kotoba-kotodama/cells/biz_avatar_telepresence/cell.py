"""
biz_avatar_telepresence — Robotics orchestration.

Pregel graph: receive_meeting_request → dispatch_avatar_robot (recipe = face_display_id + neck_tilt) → avatar_telemetry → emit_meeting_attended.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"biz_avatar_telepresence cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of joseph not attested."
    )
