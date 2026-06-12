"""
agri_autonomous_cultivation — Robotics orchestration.

Pregel graph: receive_planting_plan → dispatch_tractor (recipe = soil_moisture + seed_depth) → field_telemetry → emit_planting_completed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"agri_autonomous_cultivation cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of simeon not attested."
    )
