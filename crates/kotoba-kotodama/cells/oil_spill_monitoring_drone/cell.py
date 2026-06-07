"""
oil_spill_monitoring_drone — Hybrid Robotics orchestration.

Pregel graph: receive_alert_coords → dispatch_spill_uav (recipe = spectral_filter + plume_calc) → coverage_telemetry → emit_spill_extent_mapped.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"oil_spill_monitoring_drone cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of benjamin not attested."
    )
