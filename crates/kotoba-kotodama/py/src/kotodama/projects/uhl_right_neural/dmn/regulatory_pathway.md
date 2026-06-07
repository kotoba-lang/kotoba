---
id: uhl-r-regulatory-pathway-dmn
title: V15 PMDA/FDA regulatory pathway — DMN decision table
status: active
doc_type: reference
topic: uhl-right-neural-regulatory-pathway
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - V15 RegulatoryActor classification rules
  - PMDA / FDA pathway mapping per treatment category
  - Dossier-item checklist per pathway
related:
  - ../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../../../../../../../90-docs/adr/2605181060-otarmeni-access-path.md
  - ../actors/regulatory.py
---

# V15 Regulatory pathway — DMN

Authoritative review surface for V15 classification. The runtime
implementation in `../actors/regulatory.py` MUST match this table.

## Inputs (priority order — first active plan wins)

| Source | Field | Active when |
|---|---|---|
| V09 reprogramming_plan | (any non-stub) | reprog plan present |
| V08 neurotrophin_plan | (any non-stub) | neurotrophin plan present |
| V07 otof_tx_plan | `recommendation ∈ {dfnb9_trial_eligible, dfnb9_trial_unilateral_exception, dfnb9_pediatric_age_window_closed}` | DFNB9 gate passed |
| V11 abi_plan | (any non-stub with `candidacy`) | ABI plan present |
| V10 device_plan | (any non-stub with `recommendation`) | eCI plan present |

A "stub-marker" plan (`{_stub: true, ...}` or `{_absent: true, ...}`)
is treated as absent.

## Decision table

| Active plan | treatment_category | PMDA pathway | FDA pathway | needs trial |
|---|---|---|---|---|
| V09 reprog | in_situ_genetic_reprogramming | SEISAI_TYPE_2 | IND | true |
| V08 neurotrophin | aav_neurotrophin_preservation | SEISAI_TYPE_2 | IND | true |
| V07 OTOF (eligible / exception / window-closed) | otof_gene_therapy_otarmeni | SEISAI_TYPE_2 | ACCELERATED_APPROVAL | true iff access_tier == chord_jp_trial |
| V11 ABI (optimal / suboptimal_age) | auditory_brainstem_implant | MEDICAL_DEVICE_CLASS_4 | PMA | false |
| V11 ABI (other candidacy) | auditory_brainstem_implant | MEDICAL_DEVICE_CLASS_4 | PMA | true |
| V10 eCI | electrical_cochlear_implant | MEDICAL_DEVICE_CLASS_4 | PMA | false |
| (none) | none_determined | REQUIRES_HUMAN_REVIEW | REQUIRES_HUMAN_REVIEW | false |

## Dossier-item checklist per pathway

| treatment_category | items |
|---|---|
| in_situ_genetic_reprogramming | NON_CLINICAL_GLP, CMC_BIOLOGICS, PHASE_1_2_SAFETY, INFORMED_CONSENT, ETHICS_COMMITTEE_APPROVAL, REMS |
| aav_neurotrophin_preservation | NON_CLINICAL_GLP, CMC_BIOLOGICS, PHASE_1_2_SAFETY, INFORMED_CONSENT, ETHICS_COMMITTEE_APPROVAL |
| otof_gene_therapy_otarmeni | NON_CLINICAL_GLP, PHASE_3_EFFICACY, CMC_BIOLOGICS, LABELLING, REMS, POST_MARKET_SURVEILLANCE, INFORMED_CONSENT, ETHICS_COMMITTEE_APPROVAL |
| auditory_brainstem_implant | CMC_DEVICE, IFU, LABELLING, POST_MARKET_SURVEILLANCE, INFORMED_CONSENT, ETHICS_COMMITTEE_APPROVAL |
| electrical_cochlear_implant | CMC_DEVICE, IFU, LABELLING, POST_MARKET_SURVEILLANCE, INFORMED_CONSENT |

## Personal-import advisory

When V07 `access_tier == personal_import`, V15 sets
`requires_personal_import_advisory = true`. Per ADR-2605181060 §Tier 3
this is the deprecated path and the actor surfaces the legal-risk
advisory so the institution can warn the patient before any further
escalation.

## Provenance

- ADR-2605181000 §V15 (charter)
- ADR-2605181060 §Tier 1-3 (Otarmeni access)
- PMDA 再生医療等製品分類: 第二種 / 第三種 distinction
- FDA RMAT / Accelerated Approval / PMA / IDE / IND classifications
