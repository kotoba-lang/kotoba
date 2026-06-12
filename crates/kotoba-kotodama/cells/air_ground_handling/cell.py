"""
air_ground_handling — Aviation Robotics orchestration.

Pregel graph: receive_gate_dispatch → dispatch_tug_robot (recipe = tow_tension + pushback_path) → ground_telemetry → emit_pushback_completed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"air_ground_handling cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
