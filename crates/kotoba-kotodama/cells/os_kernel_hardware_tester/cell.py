"""
os_kernel_hardware_tester — Robotics orchestration.

Pregel graph: receive_kernel_panic → dispatch_hw_resetter (recipe = pin_config + voltage_cycle) → os_telemetry → emit_hw_reboot_success.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"os_kernel_hardware_tester cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
