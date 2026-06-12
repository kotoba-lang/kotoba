"""V09 ReprogrammingActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.reprogramming import (
    ReprogrammingActor,
    ReprogrammingBridgeTrack,
    ReprogrammingRecommendation,
)
from kotodama.projects.uhl_right_neural.actors.substrate_classifier import (
    SubstrateClass,
)


def _state(
    *,
    substrate: SubstrateClass | None = SubstrateClass.SGN_ABSENT_NERVE_PRESENT,
    age: float | None = 25.0,
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


def test_research_track_eligible_when_substrate_match_adult():
    delta = ReprogrammingActor.compute(_state(age=30.0))
    plan = delta["reprogramming_plan"]
    assert (
        plan["recommendation"]
        == ReprogrammingRecommendation.RESEARCH_TRACK_ELIGIBLE.value
    )
    assert (
        plan["bridge_track"]
        == ReprogrammingBridgeTrack.OPTO_CI_DE_TRIAL.value
    )
    assert plan["research_path_id"] == "optoci-de-trial"


def test_age_ineligible_when_pediatric():
    delta = ReprogrammingActor.compute(_state(age=4.0))
    plan = delta["reprogramming_plan"]
    assert (
        plan["recommendation"]
        == ReprogrammingRecommendation.AGE_INELIGIBLE_ADULT_FIRST.value
    )
    assert (
        plan["bridge_track"] == ReprogrammingBridgeTrack.ECI_FALLBACK.value
    )
    assert plan["research_path_id"] == "sgn-regen-uk-research"


def test_substrate_mismatch_when_wrong_class():
    delta = ReprogrammingActor.compute(
        _state(substrate=SubstrateClass.SGN_PRESENT_HC_LOSS)
    )
    plan = delta["reprogramming_plan"]
    assert (
        plan["recommendation"]
        == ReprogrammingRecommendation.SUBSTRATE_MISMATCH.value
    )


def test_not_tested_when_substrate_missing():
    delta = ReprogrammingActor.compute(_state(substrate=None))
    plan = delta["reprogramming_plan"]
    assert (
        plan["recommendation"] == ReprogrammingRecommendation.NOT_TESTED.value
    )


def test_primary_construct_documented():
    delta = ReprogrammingActor.compute(_state(age=25.0))
    plan = delta["reprogramming_plan"]
    assert "Ascl1" in plan["primary_construct"]
    assert "Sox2+" in plan["primary_construct"]
    assert plan["preclinical_status"] is True
