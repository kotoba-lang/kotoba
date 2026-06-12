"""V15 RegulatoryActor — PMDA / FDA pathway classification.

Authoritative per ADR-2605181000 §V15. Looks at the active treatment
plan (V07 OTOF / V08 BDNF / V09 reprog / V10 device / V11 ABI) and
classifies it into the appropriate Japanese (PMDA) and US (FDA)
regulatory pathway, then lists the documents + clinical trial
requirements that the plan implies.

Decision support only. The actual filing is the responsibility of the
treating institution + the product sponsor. No LLM in P0; this is
pure rule classification against the project's known pathways.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Output schema ────────────────────────────────────────────────────────────


class PmdaPathway(str, Enum):
    """Japanese PMDA pathway buckets the project's treatments map onto."""

    SEISAI_TYPE_2 = "regenerative_medical_product_type_2"  # 再生医療等製品 第二種
    SEISAI_TYPE_3 = "regenerative_medical_product_type_3"  # 第三種
    MEDICAL_DEVICE_CLASS_4 = "medical_device_class_4"      # 高度管理 (CI / ABI)
    DRUG_NEW_ACTIVE = "drug_new_active_ingredient"
    NOT_APPLICABLE = "pmda_not_applicable"
    REQUIRES_HUMAN_REVIEW = "pmda_requires_human_review"


class FdaPathway(str, Enum):
    """FDA pathways the project's treatments map onto."""

    ACCELERATED_APPROVAL = "accelerated_approval"  # Otarmeni 2026-04
    RMAT = "regenerative_medicine_advanced_therapy"
    PMA = "premarket_approval"                     # CI / ABI as Class III
    IDE = "investigational_device_exemption"       # trial-stage device
    IND = "investigational_new_drug"               # trial-stage drug/biologic
    NOT_APPLICABLE = "fda_not_applicable"
    REQUIRES_HUMAN_REVIEW = "fda_requires_human_review"


class RegulatoryDossierItem(str, Enum):
    """Document classes that the dossier check-list typically demands."""

    NON_CLINICAL_GLP = "non_clinical_glp_dossier"
    PHASE_1_2_SAFETY = "phase_1_2_safety_report"
    PHASE_3_EFFICACY = "phase_3_efficacy_report"
    CMC_BIOLOGICS = "cmc_biologics_module"
    CMC_DEVICE = "cmc_device_module"
    REMS = "risk_evaluation_and_mitigation_strategy"
    POST_MARKET_SURVEILLANCE = "post_market_surveillance_plan"
    IFU = "instructions_for_use"
    LABELLING = "labelling"
    INFORMED_CONSENT = "informed_consent_pack"
    ETHICS_COMMITTEE_APPROVAL = "ethics_committee_approval"


class RegulatoryPlan(BaseModel):
    """V15 output. Returned in state under `regulatory_path`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    treatment_category: str
    pmda_pathway: PmdaPathway
    fda_pathway: FdaPathway
    dossier_checklist: list[RegulatoryDossierItem]
    requires_clinical_trial: bool = Field(
        ...,
        description=(
            "True when the treatment plan implies a new IND/CTN or device "
            "trial registration. False when the plan reuses an already-"
            "approved product on-label."
        ),
    )
    requires_personal_import_advisory: bool = Field(
        default=False,
        description=(
            "True for Otarmeni Tier 3 (deprecated) path — V15 surfaces the "
            "personal-import legal-risk advisory to the patient + clinician."
        ),
    )
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class RegulatoryActor:
    """V15 — PMDA + FDA classification + dossier check-list."""

    name = "V15_regulatory"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        otof = state.get("otof_tx_plan") or {}
        abi_plan = state.get("abi_plan") or {}
        device_plan = state.get("device_plan") or {}
        neurotrophin_plan = state.get("neurotrophin_plan") or {}
        reprog_plan = state.get("reprogramming_plan") or {}

        plan = RegulatoryActor._classify(
            otof=otof,
            abi_plan=abi_plan,
            device_plan=device_plan,
            neurotrophin_plan=neurotrophin_plan,
            reprog_plan=reprog_plan,
        )
        return {
            "regulatory_path": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _classify(
        *,
        otof: dict[str, Any],
        abi_plan: dict[str, Any],
        device_plan: dict[str, Any],
        neurotrophin_plan: dict[str, Any],
        reprog_plan: dict[str, Any],
    ) -> RegulatoryPlan:
        # Branch order mirrors the substrate routing in pregel.py — the
        # most-specific branch wins. Reprog (V09) > Neurotrophin (V08) >
        # OTOF (V07) > ABI (V11) > eCI (V10). The actor classifies the
        # primary treatment; combo regimens add to the dossier list.

        if RegulatoryActor._is_active(reprog_plan, key="reprogramming_plan"):
            return RegulatoryPlan(
                treatment_category="in_situ_genetic_reprogramming",
                pmda_pathway=PmdaPathway.SEISAI_TYPE_2,
                fda_pathway=FdaPathway.IND,
                dossier_checklist=[
                    RegulatoryDossierItem.NON_CLINICAL_GLP,
                    RegulatoryDossierItem.CMC_BIOLOGICS,
                    RegulatoryDossierItem.PHASE_1_2_SAFETY,
                    RegulatoryDossierItem.INFORMED_CONSENT,
                    RegulatoryDossierItem.ETHICS_COMMITTEE_APPROVAL,
                    RegulatoryDossierItem.REMS,
                ],
                requires_clinical_trial=True,
                rationale=(
                    "V09 in situ reprogramming (Ascl1 + Pou4f1 + Myt1l) is "
                    "preclinical. PMDA pathway is 再生医療等製品 第二種; "
                    "FDA path is IND with RMAT eligibility likely. "
                    "Phase 1-2 first-in-human required."
                ),
            )

        if RegulatoryActor._is_active(neurotrophin_plan, key="neurotrophin_plan"):
            return RegulatoryPlan(
                treatment_category="aav_neurotrophin_preservation",
                pmda_pathway=PmdaPathway.SEISAI_TYPE_2,
                fda_pathway=FdaPathway.IND,
                dossier_checklist=[
                    RegulatoryDossierItem.NON_CLINICAL_GLP,
                    RegulatoryDossierItem.CMC_BIOLOGICS,
                    RegulatoryDossierItem.PHASE_1_2_SAFETY,
                    RegulatoryDossierItem.INFORMED_CONSENT,
                    RegulatoryDossierItem.ETHICS_COMMITTEE_APPROVAL,
                ],
                requires_clinical_trial=True,
                rationale=(
                    "V08 BDNF / NT-3 AAV is preclinical (charter P2). "
                    "PMDA 再生医療等製品 第二種 + FDA IND with RMAT "
                    "eligibility once non-clinical package is mature."
                ),
            )

        # OTOF dominant rule — gene therapy regulatory profile.
        otof_rec = otof.get("recommendation")
        if otof_rec in (
            "dfnb9_trial_eligible",
            "dfnb9_trial_unilateral_exception",
            "dfnb9_pediatric_age_window_closed",
        ):
            access_tier = otof.get("access_tier")
            return RegulatoryPlan(
                treatment_category="otof_gene_therapy_otarmeni",
                pmda_pathway=PmdaPathway.SEISAI_TYPE_2,
                fda_pathway=FdaPathway.ACCELERATED_APPROVAL,
                dossier_checklist=[
                    RegulatoryDossierItem.NON_CLINICAL_GLP,
                    RegulatoryDossierItem.PHASE_3_EFFICACY,
                    RegulatoryDossierItem.CMC_BIOLOGICS,
                    RegulatoryDossierItem.LABELLING,
                    RegulatoryDossierItem.REMS,
                    RegulatoryDossierItem.POST_MARKET_SURVEILLANCE,
                    RegulatoryDossierItem.INFORMED_CONSENT,
                    RegulatoryDossierItem.ETHICS_COMMITTEE_APPROVAL,
                ],
                requires_clinical_trial=(access_tier == "chord_jp_trial"),
                requires_personal_import_advisory=(
                    access_tier == "personal_import"
                ),
                rationale=(
                    "OTOF biallelic DFNB9 confirmed. Otarmeni is FDA "
                    "accelerated-approval (2026-04-23). PMDA review on "
                    "再生医療等製品 第二種 pathway; CHORD JP trial "
                    "enrollment uses 治験届 path. Personal import is "
                    "deprecated (ADR-2605181060 Tier 3)."
                ),
            )

        # ABI / CI — Class III medical device.
        if RegulatoryActor._is_active(abi_plan, key="abi_plan"):
            candidacy = abi_plan.get("candidacy")
            return RegulatoryPlan(
                treatment_category="auditory_brainstem_implant",
                pmda_pathway=PmdaPathway.MEDICAL_DEVICE_CLASS_4,
                fda_pathway=FdaPathway.PMA,
                dossier_checklist=[
                    RegulatoryDossierItem.CMC_DEVICE,
                    RegulatoryDossierItem.IFU,
                    RegulatoryDossierItem.LABELLING,
                    RegulatoryDossierItem.POST_MARKET_SURVEILLANCE,
                    RegulatoryDossierItem.INFORMED_CONSENT,
                    RegulatoryDossierItem.ETHICS_COMMITTEE_APPROVAL,
                ],
                # ABI hardware is PMA-approved (Cochlear ABI22) — on-label use
                # for a candidate-eligible patient does NOT require a new trial.
                requires_clinical_trial=(
                    candidacy not in (None, "optimal", "suboptimal_age")
                ),
                rationale=(
                    "Pediatric ABI uses already-approved hardware "
                    "(Cochlear ABI22 PMA / NMPA-equivalent). Overseas "
                    "referral path (Manchester / GSTT, ADR-2605181050) "
                    "operates under UK NHS regulatory authority; domestic "
                    "follow-up requires PMDA-class IV device approval "
                    "(already in place)."
                ),
            )

        if RegulatoryActor._is_active(device_plan, key="device_plan"):
            recommendation = device_plan.get("recommendation")
            return RegulatoryPlan(
                treatment_category="electrical_cochlear_implant",
                pmda_pathway=PmdaPathway.MEDICAL_DEVICE_CLASS_4,
                fda_pathway=FdaPathway.PMA,
                dossier_checklist=[
                    RegulatoryDossierItem.CMC_DEVICE,
                    RegulatoryDossierItem.IFU,
                    RegulatoryDossierItem.LABELLING,
                    RegulatoryDossierItem.POST_MARKET_SURVEILLANCE,
                    RegulatoryDossierItem.INFORMED_CONSENT,
                ],
                requires_clinical_trial=False,
                rationale=(
                    f"eCI fitting (V10 recommendation={recommendation}). "
                    "Hardware is PMA-approved (Cochlear / Advanced Bionics / "
                    "MED-EL); PMDA 高度管理医療機器 class IV. Routine "
                    "clinical use — no new regulatory submission required."
                ),
            )

        # No active treatment plan upstream.
        return RegulatoryPlan(
            treatment_category="none_determined",
            pmda_pathway=PmdaPathway.REQUIRES_HUMAN_REVIEW,
            fda_pathway=FdaPathway.REQUIRES_HUMAN_REVIEW,
            dossier_checklist=[],
            requires_clinical_trial=False,
            rationale=(
                "No active treatment plan reached V15 (V07-V11 outputs all "
                "absent or stub). Re-run upstream treatment-arm vertices "
                "before regulatory classification."
            ),
        )

    @staticmethod
    def _is_active(plan_dict: dict[str, Any], *, key: str) -> bool:
        """A plan is 'active' if it is present, not a stub-marker, and not
        empty / absent. The stub-marker shape comes from pregel.py's
        _make_stub helper (`{"_stub": True, "_vertex": "V08_..."}`)."""
        if not plan_dict:
            return False
        if plan_dict.get("_stub") is True:
            return False
        if plan_dict.get("_absent") is True:
            return False
        # Either there's a `recommendation` field (V08/V09/V10) or a
        # `candidacy` field (V11). Either signals a real downstream actor
        # populated the slot.
        return (
            "recommendation" in plan_dict
            or "candidacy" in plan_dict
            or "primary_construct" in plan_dict
        )
