"""
MaritimeCargoHandlingCell — Terminal AGV and Straddle Carrier orchestration.

Paired with `20-actors/cargo/` and `20-actors/port/`.

Pregel graph: receive_transfer_order → dispatch_agv (recipe = routing path +
collision avoidance + pickup/dropoff coords) → position_telemetry → emit_transfer_completed.

Tier: B. Murakumo node (proposed): dan.
Charter Rider §2(a)(c): HIGH (Autonomous ground vehicle swarm, proximity to workers).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "maritime_cargo_handling cell scaffold-only — HIGH §2(a) risk category. "
        "Council fleet.toml addition of `dan` not attested."
    )
