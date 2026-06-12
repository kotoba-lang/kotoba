"""V08 NeurotrophinActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.neurotrophin import (
    NeurotrophinActor,
    NeurotrophinConstruct,
    NeurotrophinRecommendation,
)
from kotodama.projects.uhl_right_neural.actors.substrate_classifier import (
    SubstrateClass,
)


def _state(
    *,
    substrate: SubstrateClass | None = SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT,
    age: float | None = 4.0,
) -> dict:
    out: dict = {
        "substrate_decision": (
            {"substrate_class": substrate.value} if substrate else {}
        ),
        "phenotype": {
            "patient_ref": "p",
            "side": "right",
            "onset": "congenital",
            "in_project_scope": True,
        },
    }
    if age is not None:
        out["phenotype"]["age_years"] = age
    return out


def test_research_track_eligible_when_substrate_match_pediatric():
    delta = NeurotrophinActor.compute(_state(age=4.0))
    plan = delta["neurotrophin_plan"]
    assert (
        plan["recommendation"]
        == NeurotrophinRecommendation.RESEARCH_TRACK_ELIGIBLE.value
    )
    assert plan["parallel_eci_track"] is True
    assert plan["research_path_id"] == "sgn-regen-uk-research"
    assert plan["primary_construct"] == NeurotrophinConstruct.UNDETERMINED.value
    assert plan["preclinical_status"] is True


def test_preclinical_only_when_adult():
    delta = NeurotrophinActor.compute(_state(age=30.0))
    plan = delta["neurotrophin_plan"]
    assert (
        plan["recommendation"]
        == NeurotrophinRecommendation.PRECLINICAL_ONLY.value
    )
    assert plan["parallel_eci_track"] is True


def test_substrate_mismatch_when_wrong_class():
    delta = NeurotrophinActor.compute(
        _state(substrate=SubstrateClass.NERVE_APLASIA)
    )
    plan = delta["neurotrophin_plan"]
    assert (
        plan["recommendation"]
        == NeurotrophinRecommendation.SUBSTRATE_MISMATCH.value
    )
    assert plan["parallel_eci_track"] is False


def test_not_tested_when_substrate_missing():
    delta = NeurotrophinActor.compute(_state(substrate=None))
    plan = delta["neurotrophin_plan"]
    assert plan["recommendation"] == NeurotrophinRecommendation.NOT_TESTED.value


def test_not_tested_when_age_missing():
    delta = NeurotrophinActor.compute(_state(age=None))
    plan = delta["neurotrophin_plan"]
    assert plan["recommendation"] == NeurotrophinRecommendation.NOT_TESTED.value


def test_human_review_flag_always_set():
    delta = NeurotrophinActor.compute(_state(age=2.0))
    assert delta["requires_human_review"] is True
