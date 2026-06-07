"""V07 OtofTxActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.otof_tx import (
    OtofAccessTier,
    OtofRecommendation,
    OtofTxActor,
)


def _v02_dfnb9_positive(panel_run_id: str = "p1") -> dict:
    return {
        "panel_run_id": panel_run_id,
        "verdicts": [],
        "biallelic_otof_pathogenic": True,
    }


def _v02_dfnb9_negative() -> dict:
    return {
        "panel_run_id": "p2",
        "verdicts": [],
        "biallelic_otof_pathogenic": False,
    }


def _phenotype(age: float = 3.0, side: str = "right") -> dict:
    return {
        "age_years": age,
        "side": side,
        "patient_ref": "p-test",
        "in_project_scope": side == "right",
    }


def test_not_tested_when_v02_absent():
    delta = OtofTxActor.compute({})
    plan = delta["otof_tx_plan"]
    assert plan["recommendation"] == OtofRecommendation.NOT_TESTED.value
    assert plan["access_tier"] == OtofAccessTier.NOT_APPLICABLE.value
    assert plan["dfnb9_gate_passed"] is False


def test_not_dfnb9_when_v02_negative():
    delta = OtofTxActor.compute(
        {
            "genetic_result": _v02_dfnb9_negative(),
            "phenotype": _phenotype(),
        }
    )
    plan = delta["otof_tx_plan"]
    assert plan["recommendation"] == OtofRecommendation.NOT_DFNB9.value
    assert plan["access_tier"] == OtofAccessTier.NOT_APPLICABLE.value


def test_unilateral_exception_when_right_side_dfnb9():
    delta = OtofTxActor.compute(
        {
            "genetic_result": _v02_dfnb9_positive(),
            "phenotype": _phenotype(age=4.0, side="right"),
        }
    )
    plan = delta["otof_tx_plan"]
    assert (
        plan["recommendation"]
        == OtofRecommendation.DFNB9_TRIAL_UNILATERAL_EXCEPTION.value
    )
    assert plan["access_tier"] == OtofAccessTier.CHORD_JP_TRIAL.value
    assert plan["unilateral_exception"] is True
    assert plan["requires_sponsor_inquiry"] is True


def test_bilateral_pediatric_dfnb9_eligible():
    delta = OtofTxActor.compute(
        {
            "genetic_result": _v02_dfnb9_positive(),
            "phenotype": _phenotype(age=2.0, side="bilateral"),
        }
    )
    plan = delta["otof_tx_plan"]
    assert (
        plan["recommendation"] == OtofRecommendation.DFNB9_TRIAL_ELIGIBLE.value
    )
    assert plan["access_tier"] == OtofAccessTier.CHORD_JP_TRIAL.value
    assert plan["unilateral_exception"] is False


def test_adult_age_window_closed_goes_to_pmda_tier():
    delta = OtofTxActor.compute(
        {
            "genetic_result": _v02_dfnb9_positive(),
            "phenotype": _phenotype(age=25.0, side="bilateral"),
        }
    )
    plan = delta["otof_tx_plan"]
    assert (
        plan["recommendation"]
        == OtofRecommendation.DFNB9_PEDIATRIC_AGE_WINDOW_CLOSED.value
    )
    assert plan["access_tier"] == OtofAccessTier.PMDA_ROUTINE.value


def test_human_review_flag_always_set():
    delta = OtofTxActor.compute(
        {
            "genetic_result": _v02_dfnb9_positive(),
            "phenotype": _phenotype(),
        }
    )
    assert delta["requires_human_review"] is True
