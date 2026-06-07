# mitate_treatment_router — Pregel cell for 5-condition treatment routing

Per all 5 condition sub-ADRs (2605260115/130/145/160/175) — treatment ladder per condition.

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **levi** (audit-style decision).

Decision tree: condition × severity → advisory tier (self-care / OTC / Rx routing / surgical referral).

Constitutional enforcements:
- **G3 disclaimer text** mandatory in `treatmentPlan` lexicon
- **G4 licensed MD co-sign** (R2+) for Rx-tier / surgical-tier advisory
- **G8 INN-only** content lint (brand name 不可 except yakushi-distributed products)
- **G11 Wellbecoming** — cost transparency (insurance / 高額療養費 / 期間 visible)
