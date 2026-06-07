"""
fin_credit_dispenser_bot — Robotics orchestration.

Pregel graph: receive_withdrawal_req → dispatch_token_dispenser (recipe = amount_value + security_gate) → fin_telemetry → emit_transaction_physicalized.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"fin_credit_dispenser_bot cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
