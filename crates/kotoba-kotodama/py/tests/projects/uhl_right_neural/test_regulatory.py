"""V15 RegulatoryActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.regulatory import (
    FdaPathway,
    PmdaPathway,
    RegulatoryActor,
    RegulatoryDossierItem,
)


def test_no_treatment_plan_needs_human_review():
    delta = RegulatoryActor.compute({})
    plan = delta["regulatory_path"]
    assert plan["pmda_pathway"] == PmdaPathway.REQUIRES_HUMAN_REVIEW.value
    assert plan["fda_pathway"] == FdaPathway.REQUIRES_HUMAN_REVIEW.value


def test_otof_tier_1_trial_path():
    delta = RegulatoryActor.compute(
        {
            "otof_tx_plan": {
                "recommendation": "dfnb9_trial_eligible",
                "access_tier": "chord_jp_trial",
                "dfnb9_gate_passed": True,
                "in_chord_age_window": True,
                "unilateral_exception": False,
                "requires_sponsor_inquiry": True,
                "requires_ethics_committee": True,
                "rationale": "",
            }
        }
    )
    plan = delta["regulatory_path"]
    assert plan["treatment_category"] == "otof_gene_therapy_otarmeni"
    assert plan["pmda_pathway"] == PmdaPathway.SEISAI_TYPE_2.value
    assert plan["fda_pathway"] == FdaPathway.ACCELERATED_APPROVAL.value
    assert plan["requires_clinical_trial"] is True
    assert plan["requires_personal_import_advisory"] is False
    assert (
        RegulatoryDossierItem.REMS.value in plan["dossier_checklist"]
    )


def test_abi_pma_path_no_trial_when_optimal():
    delta = RegulatoryActor.compute(
        {
            "abi_plan": {
                "candidacy": "optimal",
                "surgical_center_preference": "manchester_university_nhs",
                "ineligibility_reasons": [],
                "burden_disclosure_required": True,
                "domestic_followup_required": True,
                "referral_ethics_review_required": True,
                "rationale": "",
            }
        }
    )
    plan = delta["regulatory_path"]
    assert plan["treatment_category"] == "auditory_brainstem_implant"
    assert plan["pmda_pathway"] == PmdaPathway.MEDICAL_DEVICE_CLASS_4.value
    assert plan["fda_pathway"] == FdaPathway.PMA.value
    assert plan["requires_clinical_trial"] is False


def test_eci_device_class_4_no_trial():
    delta = RegulatoryActor.compute(
        {
            "device_plan": {
                "recommendation": "electrical_ci",
                "coding_strategy_seed": "CIS",
                "t_level_initial_cl": 100,
                "c_level_initial_cl": 180,
                "fitting_cadence": "weekly",
                "sessions_first_3_months": 8,
                "rationale": "",
            }
        }
    )
    plan = delta["regulatory_path"]
    assert plan["treatment_category"] == "electrical_cochlear_implant"
    assert plan["pmda_pathway"] == PmdaPathway.MEDICAL_DEVICE_CLASS_4.value
    assert plan["fda_pathway"] == FdaPathway.PMA.value
    assert plan["requires_clinical_trial"] is False


def test_stub_marker_plans_ignored():
    delta = RegulatoryActor.compute(
        {
            "otof_tx_plan": {"_stub": True, "_vertex": "V07_otof_tx"},
            "device_plan": {"_stub": True, "_vertex": "V10_device_fitting"},
        }
    )
    plan = delta["regulatory_path"]
    assert plan["pmda_pathway"] == PmdaPathway.REQUIRES_HUMAN_REVIEW.value
