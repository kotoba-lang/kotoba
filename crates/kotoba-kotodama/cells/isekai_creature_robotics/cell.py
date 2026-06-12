"""
isekai_creature_robotics — Hybrid Robotics orchestration.

Pregel graph: receive_spawn_trigger → dispatch_creature_animatronic (recipe = pose_id + haptic_level) → world_telemetry → emit_encounter_completed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"isekai_creature_robotics cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of joseph not attested."
    )
