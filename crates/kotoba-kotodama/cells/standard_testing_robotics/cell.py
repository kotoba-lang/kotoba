"""
standard_testing_robotics — Robotics orchestration.

Pregel graph: receive_spec_doc → dispatch_compliance_tester (recipe = load_stress + cycle_count) → isco_telemetry → emit_standard_verified.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"standard_testing_robotics cell scaffold-only — MEDIUM risk category. "
        f"Council fleet.toml addition of simeon not attested."
    )
