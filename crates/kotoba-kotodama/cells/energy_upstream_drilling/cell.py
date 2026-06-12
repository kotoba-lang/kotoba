"""
EnergyUpstreamDrillingCell — Oil/Gas Upstream Drilling orchestration.

Paired with `20-actors/oil-upstream/`.

Pregel graph: receive_drilling_target → dispatch_top_drive (recipe = wob + rpm +
pump pressure + mud density) → mwd_telemetry (measurement while drilling) → emit_target_depth_reached.

Tier: B. Murakumo node (proposed): naphtali.
Charter Rider §2(a)(c): HIGH (Deep borehole operations, high-pressure environments).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "energy_upstream_drilling cell scaffold-only — HIGH §2(a) risk category. "
        "Council fleet.toml addition of `naphtali` not attested."
    )
