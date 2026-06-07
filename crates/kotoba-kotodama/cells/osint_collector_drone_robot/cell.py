"""
osint_collector_drone_robot — Robotics orchestration.

Pregel graph: receive_intel_req → dispatch_stealth_uav (recipe = ir_gain + zoom_level) → intel_telemetry → emit_imagery_captured.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"osint_collector_drone_robot cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of asher not attested."
    )
