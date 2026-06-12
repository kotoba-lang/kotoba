"""
energy_downstream_refinery — Industrial Robotics orchestration.

Pregel graph: receive_refining_recipe → dispatch_process_control (recipe = temp_grad + fractionation_set) → refinery_telemetry → emit_product_batch_ready.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"energy_downstream_refinery cell scaffold-only — CRITICAL risk category. "
        f"Council fleet.toml addition of naphtali not attested."
    )
