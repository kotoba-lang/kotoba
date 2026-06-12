"""
sys_bootstrap_ignition — Robotics orchestration.

Pregel graph: receive_power_on_self_test → dispatch_hw_ignition (recipe = pwr_rail_seq + clock_sync) → boot_telemetry → emit_system_online.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"sys_bootstrap_ignition cell scaffold-only — CRITICAL risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
