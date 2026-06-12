"""
robotics_drone_swarm — Robotics Integration.

Pregel graph: receive_swarm_mission → dispatch_uav_array (recipe = waypoint_list + formation_type) → uav_telemetry → emit_mission_success.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"robotics_drone_swarm cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of benjamin not attested."
    )
