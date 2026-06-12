---
id: uhl-r-neurotrophin-eligibility-dmn
title: V08 Neurotrophin (BDNF / NT-3) research-track triage — DMN
status: active
doc_type: reference
topic: uhl-right-neural-neurotrophin-eligibility
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V08 NeurotrophinActor research-track classification rules
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../../../../../../../90-docs/adr/2605181050-uhl-overseas-referral-paths.md
  - ../actors/neurotrophin.py
---

# V08 Neurotrophin eligibility — DMN

Authoritative review surface for V08 triage. Runtime in
`../actors/neurotrophin.py` MUST match this table. V08 is a charter
Phase 2 actor — **preclinical, no current human treatment**. The
actor surfaces research-pipeline eligibility, not a clinical
recommendation.

## Inputs

| Source | Field | Type |
|---|---|---|
| V06 substrate_decision | `substrate_class` | enum — must be `SGN_DEGENERATING_NERVE_PRESENT` |
| V01 phenotype | `age_years` | float — pediatric-first IND window |

## Constants

| Constant | Value | Source |
|---|---|---|
| Pediatric index age min | 1.0y | charter §V08 IND-enabling design |
| Pediatric index age max | 17.999y | aligns with CHORD trial precedent |

## Decision table

First-match wins.

| # | substrate | age_years | recommendation | parallel_eci_track | research_path_id |
|---|---|---|---|---|---|
| 1 | missing | — | NOT_TESTED | false | null |
| 2 | not SGN_DEGENERATING | — | SUBSTRATE_MISMATCH | false | null |
| 3 | SGN_DEGENERATING | missing | NOT_TESTED | true | null |
| 4 | SGN_DEGENERATING | in [1.0, 17.999] | RESEARCH_TRACK_ELIGIBLE | true | sgn-regen-uk-research |
| 5 | SGN_DEGENERATING | outside window | PRECLINICAL_ONLY | true | sgn-regen-uk-research |

`primary_construct` is always `UNDETERMINED` in v0.x — the IND sponsor
selects between BDNF and NT-3 when an IND opens. `preclinical_status`
is always `true` in v0.x.

`parallel_eci_track=true` whenever the substrate matches: eCI fitting
(V10) is not blocked by the preserve track — it tries to keep the SGN
substrate alive that the device depends on.

## V15 consumption

When V08 is active (non-stub, non-mismatch), V15 RegulatoryActor
classifies the treatment plan as `aav_neurotrophin_preservation`:

- PMDA: SEISAI_TYPE_2 (再生医療等製品 第二種)
- FDA: IND
- Dossier: NON_CLINICAL_GLP, CMC_BIOLOGICS, PHASE_1_2_SAFETY,
  INFORMED_CONSENT, ETHICS_COMMITTEE_APPROVAL
- `requires_clinical_trial = true`

## Provenance

- ADR-2605181000 §V08 (charter Phase 2)
- ADR-2605181050 §`sgn-regen-uk-research` (closest research path today)
- BDNF / NT-3 SGN-preservation literature (Atkinson 2014, Yamasoba 2015)
