# kawase_jurisdiction_compliance

Per-jurisdiction Council Lv7+ unanimity gate (G14) per ADR-2605282200.

## R0

Scaffold only. Activation gated on R2 (post 30-day public objection +
≥1 chigiri.ipLicenseClaim record per active juris).

## Constitutional contract

`KawaseYuiPool.sol` has NO direct jurisdiction check at the L6 contract
level. The Pregel cell is the SOLE enforcement point for G14. Every
`send()` pre-flight (via `kotoba_kawase.send`) consults this cell;
absence of an active `jurisdictionAttestation` for the
(sender_juris, recipient_juris) pair short-circuits the dispatch with
`JurisdictionNotActivated`.

## R1 activation set

| Pair | Status at R1 launch | Gating Council |
|---|---|---|
| USA ↔ USA | active | Founder seat 1 unilateral attestation (Council Lv7+ pre-Bootstrap) |
| JPN ↔ JPN | active | Founder seat 1 unilateral attestation |
| USA ↔ JPN | active | Founder seat 1 unilateral attestation |
| any EU pair | pending | Bootstrap Seats 2-5 close (2026-06-19) + chigiri.ipLicenseClaim EU memo |
| UK / KOR / CHE | pending | Council Lv7+ unanimity per-pair (R3) |

## Cross-actor reads

- `chigiri.ipLicenseClaim` — multi-juris legal analysis per ADR-2605262700
- `chigiri.taxReceipt` — tax-reporting position per active juris
