# mitate_slit_cohort_tracker — Pregel cell for SLIT 3-5 year cohort tracking

Per **ADR-2605260115 §Decision 5** (condition 1 — SLIT 3-5 yr longitudinal cohort).

Paired actor: [mitate](../../mitate/) ↔ yakushi.

Murakumo node (proposed): **levi** (audit-tier multi-year longitudinal).

Cohort tracking:
- Monthly QOL questionnaire (JRQLQ — Japan Rhinoconjunctivitis QOL Questionnaire)
- Daily adherence pingback (adherent-driven, push notification G11 carve-out for SLIT 適応 patient with explicit opt-in)
- AE longitudinal feed → yakushi `pharma_post_market_surveillance` (aggregated, G7 + G10)

R3 phase activation only. Requires allergist on Council Lv6+.

kotoba-datomic-projection hot-path read carve-out (per ADR-2605231500) for cohort time-series queries.
