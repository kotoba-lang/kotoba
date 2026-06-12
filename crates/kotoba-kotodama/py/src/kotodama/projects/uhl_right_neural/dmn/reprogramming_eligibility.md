---
id: uhl-r-reprogramming-eligibility-dmn
title: V09 in situ SGN reprogramming research-track triage — DMN
status: active
doc_type: reference
topic: uhl-right-neural-reprogramming-eligibility
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V09 ReprogrammingActor research-track classification rules
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../../../../../../../90-docs/adr/2605181050-uhl-overseas-referral-paths.md
  - ../actors/reprogramming.py
---

# V09 Reprogramming eligibility — DMN

Authoritative review surface for V09 triage. Runtime in
`../actors/reprogramming.py` MUST match this table. V09 is a charter
Phase 3 actor — **research-stage, no preclinical IND today**. The
actor surfaces research-pipeline eligibility, not a clinical
recommendation. The proposed intervention is in situ AAV-delivered
Ascl1 + Pou4f1 + Myt1l polycistronic into Sox2+ supporting cells.

## Inputs

| Source | Field | Type |
|---|---|---|
| V06 substrate_decision | `substrate_class` | enum — must be `SGN_ABSENT_NERVE_PRESENT` |
| V01 phenotype | `age_years` | float — adult-first first-in-human design |

## Constants

| Constant | Value | Source |
|---|---|---|
| Adult-first age min | 18.0y | charter §V09 + ADR-2605181050 §optoci-de-trial precedent |

## Decision table

First-match wins.

| # | substrate | age_years | recommendation | bridge_track | research_path_id |
|---|---|---|---|---|---|
| 1 | missing | — | NOT_TESTED | NONE_ASSIGNED | null |
| 2 | not SGN_ABSENT_NERVE_PRESENT | — | SUBSTRATE_MISMATCH | NONE_ASSIGNED | null |
| 3 | SGN_ABSENT_NERVE_PRESENT | missing | NOT_TESTED | NONE_ASSIGNED | null |
| 4 | SGN_ABSENT_NERVE_PRESENT | ≥ 18.0 | RESEARCH_TRACK_ELIGIBLE | OPTO_CI_DE_TRIAL | optoci-de-trial |
| 5 | SGN_ABSENT_NERVE_PRESENT | < 18.0 | AGE_INELIGIBLE_ADULT_FIRST | ECI_FALLBACK | sgn-regen-uk-research |

`primary_construct` is always `Ascl1+Pou4f1+Myt1l polycistronic, Sox2+
targeted` in v0.x. `preclinical_status` is always `true`.

`bridge_track` declares what to do today while the reprogramming
pipeline matures:

- `OPTO_CI_DE_TRIAL` — Göttingen / EKFZ OT optogenetic CI (the closest
  contemporary "new auditory neuron substrate" research)
- `ECI_FALLBACK` — device only, accepts lower outcome ceiling
- `ABI_BRIDGE` — reserved for cases where the nerve becomes aplastic
  during the wait (re-route to V11)

## V15 consumption

When V09 is active (non-stub, non-mismatch), V15 RegulatoryActor
classifies the treatment plan as `in_situ_genetic_reprogramming`:

- PMDA: SEISAI_TYPE_2 (再生医療等製品 第二種)
- FDA: IND (with RMAT eligibility likely)
- Dossier: NON_CLINICAL_GLP, CMC_BIOLOGICS, PHASE_1_2_SAFETY,
  INFORMED_CONSENT, ETHICS_COMMITTEE_APPROVAL, REMS
- `requires_clinical_trial = true`

## Provenance

- ADR-2605181000 §V09 (charter Phase 3)
- ADR-2605181050 §`optoci-de-trial` (Göttingen, closest contemporary)
- Vierbuchen 2010 / Wapinski 2013 neuronal trio (Ascl1 + Pou4f1 + Myt1l)
- Sox2+ supporting cell targeting (Atoh1 lineage literature)
