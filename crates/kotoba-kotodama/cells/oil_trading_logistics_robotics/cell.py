"""
oil_trading_logistics_robotics — Hybrid Robotics orchestration.

Pregel graph: receive_delivery_contract → dispatch_transfer_pump (recipe = flow_limit + temp_seal) → trade_telemetry → emit_delivery_witnessed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"oil_trading_logistics_robotics cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
