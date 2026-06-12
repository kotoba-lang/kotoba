"""
logistics_bunker_fueling — Industrial Robotics orchestration.

Pregel graph: receive_fuel_order → dispatch_fuel_arm (recipe = flow_rate + flange_lock) → bunker_telemetry → emit_fueling_completed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"logistics_bunker_fueling cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
