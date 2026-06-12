"""
const_bim_integration — Const Integration.

Pregel graph: receive_bim_delta → dispatch_site_robot (recipe = ifc_guid + transform_matrix) → bim_telemetry → emit_as_built_update.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"const_bim_integration cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of levi not attested."
    )
