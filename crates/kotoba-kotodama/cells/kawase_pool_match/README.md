# kawase_pool_match

Continuous bipartite deposit ↔ withdrawIntent matcher (L4) per
ADR-2605282200.

## R0

Scaffold only. Importing `cell.py` raises `RuntimeError` until Council
Lv6+ ≥3 ratify the kawase-yui R1 wave (Bootstrap Council RFP closes
2026-06-19).

## R1 wiring (post-Council ratify)

| Stage | Behavior |
|---|---|
| **load** | read open `depositAttestation` + `withdrawIntent` Quads for the epoch |
| **match** | greedy oldest-first within `Constitution.getConstant(KAWASE_MAX_BAND_BPS)` (= 50 bps) |
| **emit** | `matchExecution(settlement_mode = "matched")` for paired flows; `"reserve-disbursed"` for the rest |
| **debit** | per-tick mKOTO debit against operator DID per ADR-2605282100 L1 meter |
| **report** | hourly aggregate `poolStateReport` per currency |

Constitutional invariants the cell MUST honor (off-chain mirror of the
Solidity G3/G4/G5/G9/G11/G14 set):

- only emit matches where both sender_did + recipient_did hold an Adherent SBT (G3)
- never emit a match whose locked rate exceeds ±50 bps of live Chainlink (G4)
- never accrue spread profit; reserve buffer absorbs drift (G5)
- never bypass `Constitution.getMutable(KAWASE_PER_MONTH_CAP_USD_MINOR)` (G9)
- never emit a settlement-reversal record; disputes go to chigiri.disputeMediation (G11)
- never match across a jurisdiction pair without an active `jurisdictionAttestation` (G14)
