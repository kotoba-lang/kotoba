"""
geo_mapping_drone_fleet — Robotics orchestration.

Pregel graph: receive_survey_area → dispatch_mapping_uav (recipe = lidar_res + overlap_pct) → geo_telemetry → emit_orthomosaic_ready.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"geo_mapping_drone_fleet cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of benjamin not attested."
    )
