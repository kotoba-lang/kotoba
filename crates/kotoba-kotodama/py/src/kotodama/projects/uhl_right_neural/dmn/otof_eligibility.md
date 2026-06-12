---
id: uhl-r-otof-eligibility-dmn
title: V07 Otarmeni access-path eligibility — DMN decision table
status: active
doc_type: reference
topic: uhl-right-neural-otof-eligibility
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V07 OtofTxActor access-tier triage
  - DFNB9 hard gate + CHORD age window + unilateral exception rules
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../../../../../../../90-docs/adr/2605181060-otarmeni-access-path.md
  - ../actors/otof_tx.py
---

# V07 Otarmeni access-path eligibility — DMN

Authoritative review surface for the V07 triage rules. The runtime
implementation in `../actors/otof_tx.py` MUST match this table.

## Inputs

| Source | Field | Type | Provenance |
|---|---|---|---|
| V02 genetic_result | `biallelic_otof_pathogenic` | bool | ACMG 4-5 biallelic OTOF (DFNB9 hard gate) |
| V02 genetic_result | `panel_run_id` / `verdicts` | str / list | "panel was run" signal |
| V01 phenotype | `age_years` | float | CHORD pediatric age window check |
| V01 phenotype | `side` | "right" \| "left" \| "bilateral" | unilateral-exception flag |

## Constants

| Constant | Value | Source |
|---|---|---|
| CHORD age min | 0.0y | NCT05788536 inclusion |
| CHORD age max | 17.999y | NCT05788536 inclusion |
| Project laterality | `right` | ADR-2605181000 charter scope |

## Decision table

First-match wins.

| # | DFNB9 panel run | `biallelic_otof_pathogenic` | Age in CHORD window | Side | recommendation | access_tier |
|---|---|---|---|---|---|---|
| 1 | false | — | — | — | NOT_TESTED | NOT_APPLICABLE |
| 2 | true | false | — | — | NOT_DFNB9 | NOT_APPLICABLE |
| 3 | true | true | false | any | DFNB9_PEDIATRIC_AGE_WINDOW_CLOSED | PMDA_ROUTINE |
| 4 | true | true | true | right | DFNB9_TRIAL_UNILATERAL_EXCEPTION | CHORD_JP_TRIAL |
| 5 | true | true | true | not right | DFNB9_TRIAL_ELIGIBLE | CHORD_JP_TRIAL |

All non-NOT_APPLICABLE rows set `requires_sponsor_inquiry=true` and
`requires_ethics_committee=true`. Rows 4-5 set `dfnb9_gate_passed=true`.
Row 4 is the project's main cohort outcome — unilateral right DFNB9
exists but is rare; the actor surfaces it as an exception requiring a
3-way (sponsor + home ethics + Regeneron) review before enrollment.

## V15 consumption

When `recommendation ∈ {DFNB9_TRIAL_ELIGIBLE,
DFNB9_TRIAL_UNILATERAL_EXCEPTION,
DFNB9_PEDIATRIC_AGE_WINDOW_CLOSED}` the V15 RegulatoryActor classifies
the treatment as `otof_gene_therapy_otarmeni`:

- PMDA: 再生医療等製品 第二種
- FDA: accelerated_approval (current Otarmeni status)
- Dossier: REMS, post-market surveillance, labelling, Phase-3 efficacy,
  informed consent, ethics-committee approval.

## Provenance

- ADR-2605181000 §V07 (charter)
- ADR-2605181060 (Otarmeni access path)
- [FDA press release 2026-04-23](https://www.fda.gov/news-events/press-announcements/fda-approves-first-ever-gene-therapy-treatment-genetic-hearing-loss-under-national-priority-voucher)
- [Nature 2026 — Otarmeni 42-case follow-up](https://www.nature.com/articles/s41586-026-10393-y)
