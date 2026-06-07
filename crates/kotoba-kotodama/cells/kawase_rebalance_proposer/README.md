# kawase_rebalance_proposer

Pool-drift watcher → Council attestation draft → DEX rebalance dispatch
per ADR-2605282200.

## R0

Scaffold only. Activation gated on R2 (post 30-day public objection).

## R1 → R2 ladder

| Trigger | Action |
|---|---|
| `\|driftBps\|` exceeds 500 (5%) per `poolStateReport` | draft a `rebalanceAttestation` Lexicon candidate, post to chigiri Council inbox |
| ≥4 Council Lv6+ DIDs sign | consume signed record, dispatch `KawaseYuiPool.rebalance(dex, amountIn, minOut, swapRateBps, attestationCid)` |
| Aerodrome quote outside ±1% of Chainlink mid-market | reject, escalate to chigiri.disputeMediation |
| postSwapDriftBps > 100 | flag as anomalous slippage, schedule next rebalance |

Caps (G6 yield-farming-adjacent avoidance):

- `swapAmountMinor ≤ 10% of weaker pool balance`
- `swapRateBps within ±100 bps of chainlinkRateBpsAtAttest` (stricter
  than the per-tx ±50 bps band because aggregate slippage matters)
- `Aerodrome-on-Base` only as R1 default DEX; Council-approved set is
  a separate ADR registry
