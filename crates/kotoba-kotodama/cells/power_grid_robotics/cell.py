"""
power_grid_robotics — Robotics orchestration.

Pregel graph: receive_grid_fault → dispatch_inspector (recipe = ir_scan + voltage_clearance) → grid_telemetry → emit_fault_isolated.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"power_grid_robotics cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
