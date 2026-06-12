"""
ResourceMiningRoboticsCell — Autonomous Mining and Excavation orchestration.

Paired with `20-actors/rare-earth-coverage/`.

Pregel graph: receive_extraction_plan → dispatch_excavator (recipe = drill pattern +
depth + torque limits) → seismic_telemetry → emit_ore_extracted.

Tier: B. Murakumo node (proposed): gad.
Charter Rider §2(a)(c): HIGH (Heavy excavation machinery, environmental impact).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "resource_mining_robotics cell scaffold-only — HIGH §2(a) risk category. "
        "Council fleet.toml addition of `gad` not attested."
    )
