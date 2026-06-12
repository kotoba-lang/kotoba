# land_donation_processing — Pregel Cell

**Trigger**: MST listener on `com.etzhayyim.apps.etzhayyim.land-donation`

**Effect**: 6-step donation ritual orchestration → LandRegistry.donate() (geth-private) → PublicLandRegistry mint (Base L2 via AnchorBridge) → land-donation success AT Record

**Solidity contracts**: [`50-infra/etzhayyim-land-registry/`](../../../../50-infra/etzhayyim-land-registry/)

**Murakumo placement**: Leader `judah`, replica `asher`

**Per ADR**: [2605192245](../../../../90-docs/adr/2605192245-etzhayyim-global-land-sovereignty.md) (Global) + [2605192330](../../../../90-docs/adr/2605192330-etzhayyim-extended-land-sovereignty-ocean-river-air-orbit.md) (Extended) + [2605192345](../../../../90-docs/adr/2605192345-etzhayyim-steward-succession.md) (Succession)

## State machine

```
[MST event: land-donation request]
  → load_donation_request
  → validate_geojson (WGS84, ±1m, area match)
  → verify_imagery_hash (3+ months time series)
  → verify_oath_signature (canonical oath text matches)
  → verify_successor_designation (primary + ≥2 backup pre-acceptances)
  → check_charter_compliance (donor not Non-Aligned)
    │
    ├─ all valid → emit_geth_private → emit_base_l2_mirror → emit_at_record (success) → END
    └─ any invalid → emit_at_record (failure) → END
```

## Validation requirements (gating)

| Check | Source ADR |
|---|---|
| GeoJSON valid + WGS84 + ±1m | 2605192245 §2.2 Step 1 |
| GeoJSON area matches declared | 2605192245 §2.2 Step 1 |
| Imagery bundle has 3+ months time series | 2605192245 §2.2 Step 2 |
| Donor DID signed canonical oath | 2605192245 §2.2 Step 3 |
| Primary + 2 backup successors pre-accepted | 2605192345 §1.1 |
| Donor not Charter Non-Aligned | 2605192230 |

## Running

```bash
kotoba-kotodama cell deploy --cell LandDonationProcessingCell --node judah
```

## Tests (TODO)

- unit: GeoJSON edge cases (multi-polygon / hole / pole crossing)
- integration: testnet donation e2e (100m² test land)
