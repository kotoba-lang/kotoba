# mitate_outcome_qol_followup — Pregel cell for longitudinal QOL + adherence + AE tracking

Per **ADR-2605260100 §Decision 8** (yakushi cross-actor lexicon emit boundary) +
all 5 condition sub-ADRs (followup section).

Paired actor: [mitate](../../mitate/) ↔ yakushi.

Murakumo node (proposed): **levi** (audit-tier longitudinal).

Cross-actor leg (mitate → yakushi):
- `outcome_qol_followup` → yakushi `pharma_adverse_event` (individual handoff with patient consent)
- `outcome_qol_followup` → yakushi `pharma_post_market_surveillance` (aggregated, no patient identity per G7 + G10)

Cross-actor leg (yakushi → mitate):
- yakushi `pharma_adverse_event` → `outcome_qol_followup` (yakushi-side AE intake back-feed)

**Dedupe rule for AE double-counting** between mitate `outcome_qol_followup` and yakushi
`pharma_adverse_event` must be established jointly in R1 ADRs of both sides.
