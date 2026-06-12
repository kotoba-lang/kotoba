"""
kawase_pool_match — multi-stable bipartite matcher per ADR-2605282200 L4.

Pregel graph (R1 wiring):

    watch_pool_events  → load_open_deposits   → load_open_intents     →
    pair_within_band   → emit_match_execution → reserve_fallback      →
    debit_mkoto_cost   → emit_pool_state_report

Each tick (default 30 s) loads the open deposit set (depositAttestation
records that have NO matching matchExecution yet) and the open withdraw-
intent set, then greedily matches by oldest-first within ±0.5% band
(KAWASE_MAX_BAND_BPS const). Remainder flows to the reserve buffer with
`settlement_mode = "reserve-disbursed"`. Per-epoch mKOTO debit emits via
the ADR-2605282100 L1 meter.

Murakumo-only inference (ADR-2605215000 + ADR-2605282200 G12) — this
cell MUST run on a fleet.toml-listed node; the executingCellDid in every
emitted matchExecution record is checked off-chain against the fleet
roster.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "kawase_pool_match cell scaffold-only — Council Lv6+ ≥3 ratification of "
        "ADR-2605282200 R1 + KawaseYuiPool deploy required before activation."
    )
