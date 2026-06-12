"""
MaritimeVesselNavCell — Autonomous Vessel Navigation orchestration.

Paired with `20-actors/vessel/`.

Pregel graph: receive_waypoint → dispatch_propulsion (recipe = rpm + rudder angle +
dynamic positioning constraints) → ais_telemetry → emit_waypoint_reached.

Tier: B. Murakumo node (proposed): zebulun.
Charter Rider §2(a)(c): HIGH (Physical asset motion and kinetic potential).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "maritime_vessel_nav cell scaffold-only — HIGH §2(a) risk category. "
        "Council fleet.toml addition of `zebulun` not attested."
    )
