---
id: uhl-r-abi-candidacy-dmn
title: V11 ABI candidacy — DMN decision table
status: active
doc_type: reference
topic: uhl-right-neural-abi-candidacy
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V11 AbiActor candidacy triage
  - Manchester / GSTT pediatric-ABI age windows
  - CNS-comorbidity hard exclusion
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../../../../../../../90-docs/adr/2605181050-uhl-overseas-referral-paths.md
  - ../actors/abi.py
---

# V11 ABI candidacy — DMN

Authoritative review surface for the V11 triage rules. The runtime
implementation in `../actors/abi.py` MUST match this table.

## Inputs

| Source | Field | Type | Provenance |
|---|---|---|---|
| V06 substrate_decision | `substrate_class` | enum | must be NERVE_APLASIA |
| V03 imaging / V06 evidence | `cn_fiber_count` | int 0-4 | fallback nerve-aplasia hard gate when V06 absent |
| V01 phenotype | `age_years` | float | Manchester / GSTT age windows |
| V01 phenotype | `cns_comorbidity` | bool | autism spectrum / multi-disability exclusion |

## Constants

| Constant | Value | Source |
|---|---|---|
| Optimal age max | 5.0y | Cortical plasticity (Manchester pediatric ABI literature) |
| Referral age ceiling | 12.0y | Standard pediatric referral window |
| ABI hard gate fiber count | 0 | NERVE_APLASIA equivalence |

## Decision table

First-match wins.

| # | Substrate | cn_fiber_count | CNS comorbidity | age range | candidacy | center preference |
|---|---|---|---|---|---|---|
| 1 | not NERVE_APLASIA | — | — | — | INELIGIBLE_SUBSTRATE | UNRESOLVED |
| 2 | absent + cn ≠ 0 | — | — | — | REQUIRES_HUMAN_REVIEW | UNRESOLVED |
| 3 | NERVE_APLASIA (or cn=0) | — | true | — | INELIGIBLE_CNS_COMORBIDITY | UNRESOLVED |
| 4 | NERVE_APLASIA (or cn=0) | — | false | missing | REQUIRES_HUMAN_REVIEW | UNRESOLVED |
| 5 | NERVE_APLASIA (or cn=0) | — | false | > 12.0 | INELIGIBLE_AGE | UNRESOLVED |
| 6 | NERVE_APLASIA (or cn=0) | — | false | (5.0, 12.0] | SUBOPTIMAL_AGE | MANCHESTER_UNIVERSITY_NHS |
| 7 | NERVE_APLASIA (or cn=0) | — | false | ≤ 5.0 | OPTIMAL | MANCHESTER_UNIVERSITY_NHS |

All non-INELIGIBLE_SUBSTRATE rows set
`burden_disclosure_required = true`,
`domestic_followup_required = true`,
`referral_ethics_review_required = true` per
ADR-2605181050 §Burden disclosure + Preconditions 5.

## V15 consumption

V15 RegulatoryActor classifies any non-ineligible ABI plan as
`auditory_brainstem_implant`:

- PMDA: 高度管理医療機器 class 4 (already-approved hardware)
- FDA: PMA (Cochlear ABI22)
- `requires_clinical_trial = false` for OPTIMAL / SUBOPTIMAL_AGE (on-label use)

## Provenance

- ADR-2605181000 §V11 (charter)
- ADR-2605181050 §`abi-uk-nhs-paediatric`
- [Manchester ABI Service — Highly Specialised Services](https://www.mrcc.org.uk/clinical-diagnostics/highly-specialised-services/auditory-brainstem-implant-service/)
- [Royal Manchester Children's Hospital — Paediatric CI Programme](https://mft.nhs.uk/rmch/services/manchester-paediatric-cochlear-implant-programme/)
