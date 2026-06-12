# kawase_silen_review

Quarterly Council audit cell (ADR-2605282200 — R3 activation).

## R0

Scaffold only. Activation gated on R3 (post-R2 + Council Lv7+ unanimity
+ ≥1 completed annual cycle).

## R3 wiring

Per quarter (Jan/Apr/Jul/Oct ± 7 days):

1. Aggregate every `matchExecution` + `poolStateReport` +
   `rebalanceAttestation` emitted between `reviewPeriodStart` and
   `reviewPeriodEnd`.
2. Compute the aggregate metrics required by the `silenKawaseReview`
   Lexicon: `totalVolumeUsdEquivalentMinor`, per-currency volume,
   `matchedSharePctIntegerHundredths`, `avgMatchWaitSeconds`,
   `outOfBandHaltCount`, `mKotoConsumedThisEpoch` rollup, etc.
3. Assert the **const-field structural invariants**:

   | Field | Expected | Gate |
   |---|---|---|
   | `spreadProfitMkoto` | 0 | G5 (mid-market only) |
   | `commercialRemittanceSoftwarePenetrationPct` | 0 | G7 (build-time enforced by `verify_no_commercial_remittance.py`) |
   | `nonAdherentParticipationCount` | 0 | G3 (structurally impossible because the Solidity `onlyAdherent` modifier reverts) |

4. Publish the `silenKawaseReview` Lexicon record + collect ≥3 Council
   Lv6+ DID attestations.
5. Cross-actor: emit a `toritate.annualReport` source CID.

Critical findings (any const-field nonzero) halt the cell + escalate
to Council Lv7+ (constitutional violation severity).
