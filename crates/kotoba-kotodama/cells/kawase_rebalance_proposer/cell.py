"""
kawase_rebalance_proposer — pool-drift watcher per ADR-2605282200.

Pregel graph (R1 wiring):

    poll_drift_bps          → if |drift| > 500 :              →
    draft_rebalance_attest  → publish_council_candidate       →
    wait_council_sigs(≥4/7) → dispatch_KawaseYuiPool_rebalance →
    record_postSwapDriftBps

When the cumulative drift between paired pools exceeds 500 bps (5%),
the cell drafts a `rebalanceAttestation` Lexicon candidate for Council
Lv6+ ≥4/7 sign-off. Once 4+ Council DIDs sign, the cell consumes the
signed record and calls `KawaseYuiPool.rebalance(...)` on Base L2 via
the religious-corp paymaster. Aerodrome-on-Base is the R1 default DEX;
Council-approved set governed by a separate ADR.

Rebalance frequency target: ≤1/month at R1, ≤1/quarter at R2. Each
event is fully on-chain auditable + has the 4-of-7 Council attestation
chain attached.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "kawase_rebalance_proposer cell scaffold-only — Council Lv6+ ≥3 ratification of "
        "ADR-2605282200 R2 + Aerodrome-on-Base allow-list required before activation."
    )
