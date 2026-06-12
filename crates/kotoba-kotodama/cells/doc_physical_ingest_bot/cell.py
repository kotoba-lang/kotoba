"""
doc_physical_ingest_bot — Robotics orchestration.

Pregel graph: receive_scan_trigger → dispatch_feeder_arm (recipe = page_separation + dpi_setting) → ingest_telemetry → emit_doc_digitized.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"doc_physical_ingest_bot cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of simeon not attested."
    )
