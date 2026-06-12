"""
logistics_automated_warehouse — Robotics orchestration.

Pregel graph: receive_pick_order → dispatch_shuttle (recipe = shelf_id + weight_balance) → inv_telemetry → emit_order_staged.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"logistics_automated_warehouse cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
