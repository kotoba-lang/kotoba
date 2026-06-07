"""
maritime_crew_automation — Robotics orchestration.

Pregel graph: receive_crew_task → dispatch_support_robot (recipe = task_type + assist_mode) → crew_telemetry → emit_task_assisted.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"maritime_crew_automation cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of dan not attested."
    )
