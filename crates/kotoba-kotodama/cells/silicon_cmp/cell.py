"""
SiliconCmpCell — CMP (chemical-mechanical polish) orchestration.

Per ADR-2605242545 §Decision 1 row 5.

Reference vendors: Ebara / AMAT.

Pregel graph: receive_wafer_lot → dispatch_polish (recipe = slurry +
downforce + duration + endpoint algo) → endpoint telemetry → emit_wafer_lot.

Tier: B. Murakumo node (proposed): naphtali.
Charter Rider §2(a)(c): LOW.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "silicon_cmp cell scaffold-only — Council fleet.toml addition of "
        "`naphtali` not attested per ADR-2605242545 §5."
    )
