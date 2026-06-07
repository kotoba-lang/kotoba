"""
network_hardware_robotics — Robotics orchestration.

Pregel graph: receive_link_down → dispatch_patch_robot (recipe = port_id + cable_type) → net_telemetry → emit_physical_link_restored.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"network_hardware_robotics cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
