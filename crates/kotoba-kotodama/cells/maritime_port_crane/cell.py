"""
MaritimePortCraneCell — Port Gantry Crane orchestration.

Paired with `20-actors/port/`.

Pregel graph: receive_load_plan → dispatch_hoist (recipe = trolley pos + hoist height +
spreader lock state) → load_telemetry → emit_move_completed.

Tier: B. Murakumo node (proposed): issachar.
Charter Rider §2(a)(c): HIGH (Heavy physical operations, proximity to personnel).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "maritime_port_crane cell scaffold-only — HIGH §2(a) risk category. "
        "Council fleet.toml addition of `issachar` not attested."
    )
