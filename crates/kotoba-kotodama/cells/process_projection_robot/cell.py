"""
process_projection_robot — Robotics orchestration.

Pregel graph: receive_process_state → dispatch_ar_projector (recipe = mapping_coords + layer_vis) → process_telemetry → emit_projection_updated.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"process_projection_robot cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of simeon not attested."
    )
