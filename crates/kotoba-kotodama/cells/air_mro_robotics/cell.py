"""
air_mro_robotics — Aviation Robotics orchestration.

Pregel graph: receive_mro_schedule → dispatch_inspector_drone (recipe = ndt_scan + blade_clearance) → mro_telemetry → emit_airworthiness_signed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"air_mro_robotics cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of levi not attested."
    )
