"""
energy_distribution_robotics — Robotics orchestration.

Pregel graph: receive_dispatch_order → dispatch_terminal_robot (recipe = hose_connect + flow_stop) → dist_telemetry → emit_truck_loaded.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"energy_distribution_robotics cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
