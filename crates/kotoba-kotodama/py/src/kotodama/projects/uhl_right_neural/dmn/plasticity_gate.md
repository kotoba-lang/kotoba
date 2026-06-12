---
id: uhl-r-plasticity-gate-dmn
title: V12 Plasticity — age × critical-period gate
status: active
doc_type: reference
topic: uhl-right-neural-plasticity-gate
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V12 central plasticity age-window phase gate
  - V13 outcome_ceiling prior seeding
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../actors/plasticity.py
  - ../actors/outcome.py
---

# V12 Plasticity Gate — age × critical-period table

Authoritative review surface for the V12 phase gate. The runtime
implementation in `../actors/plasticity.py` MUST match this table. The
V13 OutcomeActor reads the `outcome_ceiling` column to seed its
Beta-Binomial prior.

## Rationale

The auditory critical period for binaural integration closes meaningfully
around age 7 (Kral & Sharma — ~3.5-7y window for cross-modal
reorganization to consolidate). For unilateral congenital SNHL the
contralateral cortex carries the load until binaural input is restored,
and central plasticity defines the achievable ceiling on V13 outcomes
(localization / SIN / PedsQL).

## Inputs

| Source | Field | Type | Provenance |
|---|---|---|---|
| V01 phenotype | `age_years` | float ≥ 0 | Patient chronological age |
| V05 cmv_torch | `cmv_positive` | bool | Informational — heightens contralateral progression risk |

## Decision table

First-match wins.

| # | `age_years` | `phase_gate` | `outcome_ceiling` | `phase_gate_passed` |
|---|---|---|---|---|
| 1 | < 3.5 | OPTIMAL | HIGH | true |
| 2 | [3.5, 7.0) | REDUCED | MODERATE | true |
| 3 | [7.0, 12.0) | MARGINAL | LIMITED | false |
| 4 | ≥ 12.0 | CLOSED | LATE_ADULT | false |

`phase_gate_passed = false` does NOT halt the Pregel (charter §V12). It
sets a lower ceiling on the V13 prior and propagates an explicit reduced
expectation through `outcome_posterior`.

## V13 prior seeding

V13's Beta(α, β) prior per axis is seeded from `outcome_ceiling`:

| `outcome_ceiling` | Prior (α, β) | E[p] |
|---|---|---|
| HIGH | (5.0, 2.0) | 0.714 |
| MODERATE | (3.0, 3.0) | 0.500 |
| LIMITED | (2.0, 4.0) | 0.333 |
| LATE_ADULT | (2.0, 6.0) | 0.250 |
| (unset) | (2.0, 2.0) | 0.500 |

## CMV side-effect

When `substrate_evidence.cmv_positive == true`, the actor adds a
surveillance note to `plasticity_plan.notes` indicating heightened
contralateral progression risk. The phase gate itself does not change.

## Provenance

- ADR-2605181000 §V12, §Ethical guardrails item 6 (year-based phase gate)
- Kral A, Sharma A, "Crossmodal plasticity in hearing loss" (Trends Neurosci 2012)
- Sharma A, Dorman MF, Kral A, "The influence of a sensitive period on
  central auditory development" (Hear Res 2005)
