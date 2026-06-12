"""
power_denki_grid_ops — Power Integration.

Pregel graph: receive_denki_load_shed → dispatch_smart_relay (recipe = freq_target + shed_priority) → grid_telemetry → emit_grid_stability_report.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"power_denki_grid_ops cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of judah not attested."
    )
