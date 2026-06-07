"""
datacenter_hardware_robotics — Robotics orchestration.

Pregel graph: receive_hw_fault → dispatch_swap_bot (recipe = rack_id + component_sn) → dc_telemetry → emit_component_replaced.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"datacenter_hardware_robotics cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
