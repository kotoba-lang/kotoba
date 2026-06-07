"""
waste_sorting_robotics — Robotics orchestration.

Pregel graph: receive_waste_input → dispatch_sorter (recipe = spectro_analysis + arm_speed) → recycle_telemetry → emit_sorting_completed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"waste_sorting_robotics cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of joseph not attested."
    )
