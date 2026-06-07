---
id: uhl-r-substrate-classifier-dmn
title: V06 Substrate Classifier — DMN decision table
status: active
doc_type: reference
topic: uhl-right-neural-substrate-classifier
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V06 substrate classifier decision rules (4-way + indeterminate)
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../actors/substrate_classifier.py
---

# V06 Substrate Classifier — DMN

Authoritative review surface for the 4-way neural substrate classifier
(architectural hinge per ADR-2605181000). The runtime implementation in
`../actors/substrate_classifier.py` MUST match this table.

## Inputs (evidence fan-in)

| Source | Field | Type | Provenance |
|---|---|---|---|
| V03 imaging | `cn_fiber_count` | int 0-4 | IAC CISS/FIESTA cochlear nerve fiber count |
| V04 electrophys | `eabr_present` | bool | Electrically-evoked ABR present |
| V04 electrophys | `eabr_latency_prolonged` | bool | eABR wave latency prolonged |
| V04 electrophys | `dpoae_present` | bool | Distortion product OAE present (HC proxy) |
| V02 genetic | `biallelic_otof_pathogenic` | bool | ACMG class 4-5 (gates ADR-2605181060) |
| V05 cmv/torch | `cmv_positive` | bool | Informational only — does NOT branch V06 |

`None` = signal not available (P0 MVP: V02-V05 are stubs).

## Outputs

| Field | Type | Range |
|---|---|---|
| `substrate_class` | enum | `nerve_aplasia` / `sgn_absent_nerve_present` / `sgn_degenerating_nerve_present` / `sgn_present_hc_loss` / `indeterminate` |
| `downstream_vertices` | string[] | V07-V11 routing targets |
| `confidence` | enum | `high` / `medium` / `low` |
| `rationale` | string | Human-readable explanation (≤500 chars) |

## Decision table (hit policy: FIRST)

| # | `cn_fiber_count` | `eabr_present` | `eabr_latency_prolonged` | `dpoae_present` | → `substrate_class` | Confidence | Downstream |
|---|---|---|---|---|---|---|---|
| 1 | `== 0` | * | * | * | `nerve_aplasia` | high | V11 (ABI) |
| 2 | `∈ {1, 2}` | `false` | * | * | `sgn_absent_nerve_present` | medium | V09 reprog + V10b optoCI |
| 3 | `>= 2` | `true` | `true` | * | `sgn_degenerating_nerve_present` | medium | V08 neurotrophin + V10 eCI |
| 4 | `>= 3` | `true` | * | `false` | `sgn_present_hc_loss` | high | V07 OTOF-tx (if DFNB9) + V10 eCI |
| 5 | otherwise | otherwise | otherwise | otherwise | `indeterminate` | low | (none — re-acquire evidence) |

`*` = any value including `None`.

## Notes

- Rule 1 takes absolute priority: nerve aplasia is a structural finding that
  invalidates all peripheral interventions; only V11 (ABI) bypass applies.
- Rule 2 detects the "no SGN response + nerve substrate exists" pattern that
  electrical CI cannot address but where optogenetic CI / SGN regeneration
  research tracks (V09, V10b) become candidates.
- Rule 3 detects deterioration of an existing SGN population — neurotrophin
  (BDNF/NT-3) gene therapy aims to preserve before complete loss.
- Rule 4 detects classic hair-cell loss with intact innervation — eCI
  works well here, and OTOF gene therapy is the first-line addition when
  V02 confirms biallelic DFNB9.
- Rule 5 (INDETERMINATE) is the safe default. The Pregel runner halts the
  branch and emits "re-acquire V02-V05 inputs" rather than guessing.

## V02 gate interaction (ADR-2605181060)

When rule 4 fires and `biallelic_otof_pathogenic == true`, V07 OTOF-tx
becomes the primary recommendation (subject to Otarmeni access path tiers
per ADR-2605181060). Otherwise rule 4 routes to V10 electrical CI only.
V16 enforces this gate when filtering institution capabilities.

## Out of scope (V06)

- Age-based modulation — handled by V12 (plasticity, critical-period gate).
- Bilateral vs unilateral — handled at V01 / project charter scope.
- Etiology classification — V05 (CMV/TORCH) and V02 (genetic) are upstream
  evidence sources, not V06 outputs.

## Change control

Mutations to this table require updating both this DMN doc AND
`../actors/substrate_classifier.py` in the same PR. ADR-2605181000 §V06
must be cross-referenced if the branch semantics change.
