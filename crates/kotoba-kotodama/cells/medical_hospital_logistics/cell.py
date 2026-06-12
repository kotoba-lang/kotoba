"""
medical_hospital_logistics — Robotics orchestration.

Pregel graph: receive_delivery_order → dispatch_hospital_agv (recipe = ward_id + payload_temp) → med_telemetry → emit_delivered_at_station.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"medical_hospital_logistics cell scaffold-only — HIGH risk category. "
        f"Council fleet.toml addition of levi not attested."
    )
