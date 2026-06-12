"""
low_level_go_bridge_ops — Robotics orchestration.

Pregel graph: receive_binary_exec_req → dispatch_controller_io (recipe = io_pin + pwm_freq) → bridge_telemetry → emit_io_operation_confirmed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"low_level_go_bridge_ops cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
