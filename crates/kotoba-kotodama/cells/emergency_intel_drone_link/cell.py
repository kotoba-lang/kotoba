"""
emergency_intel_drone_link — Robotics orchestration.

Pregel graph: receive_sos_graph_alert → dispatch_sos_uav (recipe = search_pattern + ir_stream) → sos_telemetry → emit_site_intelligence_fused.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"emergency_intel_drone_link cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of asher not attested."
    )
