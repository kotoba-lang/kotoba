# toritate_imputed_income_compute — toritate (R0 scaffold)

Compute per-adherent **imputed income** (FLOW) — the market-equivalent annual value
of in-kind services consumed — from the open valuation tables under
`20-actors/toritate/valuation/`. Feeds the aggregate `basicHighIncome` block of
`com.etzhayyim.liberation.metricReport`.

Per ADR-2605301020 + ADR-2605262900. R0 scaffold — `cell.py` raises at import time
until R1 (Council Lv6+ ≥3 ratify + valuation method table attested, post 2026-06-19).

- **Actor**: toritate (執帳) — `did:web:toritate.etzhayyim.com`
- **Murakumo node (proposed)**: gad (accounting tribe)
- **Output**: aggregated into `com.etzhayyim.liberation.metricReport.basicHighIncome`
- **Ceiling**: NO CASH (`cashStipendUsdMicros≡0`, N1) · AGGREGATE-ONLY (no per-adherent leaderboard, N6) · encrypted per-adherent inputs (ADR-2605181100) · Murakumo-only inference (ADR-2605215000) · open + citable valuation sources (G3/G4)
