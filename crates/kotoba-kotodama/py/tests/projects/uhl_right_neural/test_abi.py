"""V11 AbiActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.abi import (
    AbiActor,
    AbiCandidacy,
    AbiCenterPreference,
)
from kotodama.projects.uhl_right_neural.actors.substrate_classifier import (
    SubstrateClass,
)


def _state(
    *,
    substrate: SubstrateClass = SubstrateClass.NERVE_APLASIA,
    age: float = 2.0,
    cn_fiber_count: int | None = 0,
    cns_comorbidity: bool = False,
) -> dict:
    return {
        "substrate_decision": {"substrate_class": substrate.value},
        "substrate_evidence": {"cn_fiber_count": cn_fiber_count}
        if cn_fiber_count is not None
        else {},
        "phenotype": {
            "age_years": age,
            "side": "right",
            "patient_ref": "p",
            "in_project_scope": True,
            "cns_comorbidity": cns_comorbidity,
        },
    }


def test_optimal_when_aplasia_and_under_5y():
    delta = AbiActor.compute(_state(age=1.5))
    plan = delta["abi_plan"]
    assert plan["candidacy"] == AbiCandidacy.OPTIMAL.value
    assert (
        plan["surgical_center_preference"]
        == AbiCenterPreference.MANCHESTER_UNIVERSITY_NHS.value
    )
    assert plan["domestic_followup_required"] is True


def test_suboptimal_when_aplasia_and_age_5_to_12():
    delta = AbiActor.compute(_state(age=8.0))
    plan = delta["abi_plan"]
    assert plan["candidacy"] == AbiCandidacy.SUBOPTIMAL_AGE.value


def test_ineligible_age_when_over_12():
    delta = AbiActor.compute(_state(age=15.0))
    plan = delta["abi_plan"]
    assert plan["candidacy"] == AbiCandidacy.INELIGIBLE_AGE.value


def test_ineligible_substrate_when_not_aplasia():
    delta = AbiActor.compute(
        _state(substrate=SubstrateClass.SGN_PRESENT_HC_LOSS, cn_fiber_count=4)
    )
    plan = delta["abi_plan"]
    assert plan["candidacy"] == AbiCandidacy.INELIGIBLE_SUBSTRATE.value


def test_cns_comorbidity_excludes():
    delta = AbiActor.compute(_state(cns_comorbidity=True))
    plan = delta["abi_plan"]
    assert plan["candidacy"] == AbiCandidacy.INELIGIBLE_CNS_COMORBIDITY.value


def test_human_review_when_substrate_missing():
    delta = AbiActor.compute(
        {
            "substrate_decision": {},
            "substrate_evidence": {"cn_fiber_count": 3},  # not aplasia
            "phenotype": {"age_years": 2.0, "side": "right"},
        }
    )
    plan = delta["abi_plan"]
    assert plan["candidacy"] == AbiCandidacy.REQUIRES_HUMAN_REVIEW.value


def test_burden_disclosure_and_ethics_flags_always_true():
    delta = AbiActor.compute(_state(age=1.5))
    plan = delta["abi_plan"]
    assert plan["burden_disclosure_required"] is True
    assert plan["referral_ethics_review_required"] is True
