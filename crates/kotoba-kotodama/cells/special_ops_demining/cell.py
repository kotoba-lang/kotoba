"""
SpecialOpsDeminingCell — Autonomous Demining and EOD orchestration.

Paired with `20-actors/demining/`.

Pregel graph: receive_grid_survey → dispatch_probe (recipe = sensor sensitivity +
probe depth + neutralizer payload) → eod_telemetry → emit_grid_cleared.

Tier: B. Murakumo node (proposed): asher.
Charter Rider §2(a)(c): CRITICAL (Handling of explosive devices, immediate risk to life).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "special_ops_demining cell scaffold-only — CRITICAL §2(a) risk category. "
        "Council fleet.toml addition of `asher` not attested."
    )
