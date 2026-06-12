# kawase_fx_oracle_watcher

Chainlink mid-market price-feed subscriber (L3) per ADR-2605282200.

## R0

Scaffold only. Importing `cell.py` raises `RuntimeError` until Council
Lv6+ ≥3 ratify the kawase-yui R1 wave + approve the Chainlink feed
allow-list.

## R1 wiring (post-Council ratify)

Subscribes to the Chainlink `AggregatorV3Interface` for each active
pair (USD/EUR at R1; +USD/JPY R2; +USD/KRW + USD/GBP + USD/CHF R3),
emits an `fxRateAttestation` Lexicon record on each new round, and
runs the constitutional band check:

```
diff = |quoted_bps - chainlink_bps|
if diff > maxBandBps * chainlink_bps / 10000:
    emit fxRateAttestation { withinBand: false }
    halt every kawase_pool_match cell for the affected pair
    if sustained > 5 min: escalate to chigiri.disputeMediation
```

`maxBandBps` reads `Constitution.getConstant(KAWASE_MAX_BAND_BPS)`
= 50 (= ±0.5%) per ADR-2605282200 G4. Constitutional — cannot be
widened by governance.
