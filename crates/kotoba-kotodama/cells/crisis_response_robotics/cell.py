"""
crisis_response_robotics — Hybrid Robotics orchestration.

Pregel graph: receive_sos_signal → dispatch_rescue_bot (recipe = thermal_map + load_assist) → crisis_telemetry → emit_survivor_reached.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"crisis_response_robotics cell scaffold-only — CRITICAL risk category. "
        f"Council fleet.toml addition of asher not attested."
    )
