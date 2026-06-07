"""
gov_auction_display_robotics — Robotics orchestration.

Pregel graph: receive_auction_item → dispatch_display_turntable (recipe = rotate_speed + lighting_lux) → auction_telemetry → emit_item_displayed.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"gov_auction_display_robotics cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of joseph not attested."
    )
