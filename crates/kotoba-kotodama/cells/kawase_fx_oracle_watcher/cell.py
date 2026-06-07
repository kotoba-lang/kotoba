"""
kawase_fx_oracle_watcher — Chainlink mid-market subscriber (L3) per
ADR-2605282200.

Pregel graph (R1 wiring):

    subscribe_chainlink_round  → check_band(maxBandBps)         →
    emit_fx_rate_attestation   → if out_of_band: halt_match     →
    escalate_after_5min_sustain → chigiri_dispute_mediation

Halts ALL match cells on the affected pair when |quoted - chainlink| >
KAWASE_MAX_BAND_BPS (= 50 bps = ±0.5%) for >5 min sustained — Council
Lv6+ ≥3 attestation chain required to resume. Out-of-band is the
canonical signal that the constitutional mid-market invariant is at
risk; the cell prefers to halt rather than risk a spread-leaking match.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "kawase_fx_oracle_watcher cell scaffold-only — Council Lv6+ ≥3 ratification of "
        "ADR-2605282200 R1 + Chainlink feed allow-list required before activation."
    )
