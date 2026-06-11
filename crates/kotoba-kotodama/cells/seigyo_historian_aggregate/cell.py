"""
SeigyoHistorianAggregateCell — telemetry aggregation northbound.

Per ADR-2606111000 §5 (N7 inheritance) + §6 row 5.

Pregel graph: read_site_historian (TimescaleDB | InfluxDB OSS,
site-local full-rate ms–s data — NEVER leaves site) → bucket_aggregate
(≥1-minute buckets for process variables; ≥1-hour buckets for anything
attributable to an individual person's activity, per hikari N7
inheritance / ADR-2605265000 §1.3 precedent) →
emit_telemetry_aggregate_record → feed_murakumo_optimizer (advisory
proposals only; applied solely through attested setpoint envelopes
per §3.4; Murakumo-only inference per ADR-2605215000).

No camera/audio streams transit this cell (§5).

Tier: B. Murakumo node (proposed): simeon.
Charter Rider §2(a)(c): LOW (read + aggregate only; no actuation path).
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None
SILEN_SEIGYO_BASELINE_REVIEW_CID: str | None = None

if (
    COUNCIL_FLEET_ATTESTATION_TX_HASH is None
    or SILEN_SEIGYO_BASELINE_REVIEW_CID is None
):
    raise RuntimeError(
        "seigyo_historian_aggregate cell scaffold-only — Council fleet.toml + "
        "silen-seigyo baseline not attested per ADR-2606111000 §6 + §8 R0."
    )
