"""
energy_marine_loading_ops — Robotics orchestration.

Pregel graph: receive_berth_plan → dispatch_loading_arm (recipe = vessel_manifold + flow_rate) → ship_telemetry → emit_vessel_loaded.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"energy_marine_loading_ops cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
