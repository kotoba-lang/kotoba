"""V10 ConventionalDeviceActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.conventional_device import (
    ConventionalDeviceActor,
    DeviceRecommendation,
    FittingCadence,
)
from kotodama.projects.uhl_right_neural.actors.substrate_classifier import (
    SubstrateClass,
)


def test_sgn_present_hc_loss_pediatric_eci() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=SubstrateClass.SGN_PRESENT_HC_LOSS.value,
        age_years=2.5,
    )
    assert plan.recommendation is DeviceRecommendation.ECI
    assert plan.fitting_cadence is FittingCadence.WEEKLY
    assert plan.t_level_initial_cl == 100  # pediatric seed
    assert plan.sessions_first_3_months == 8


def test_sgn_present_hc_loss_adult_eci() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=SubstrateClass.SGN_PRESENT_HC_LOSS.value,
        age_years=45.0,
    )
    assert plan.recommendation is DeviceRecommendation.ECI
    assert plan.fitting_cadence is FittingCadence.BIWEEKLY
    assert plan.t_level_initial_cl == 120  # adult seed


def test_sgn_degenerating_routes_to_combined_track() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT.value,
        age_years=4.0,
    )
    assert plan.recommendation is DeviceRecommendation.ECI_WITH_NEUROTROPHIN_TRACK
    assert plan.t_level_initial_cl is not None


def test_nerve_aplasia_defers_to_v11_abi() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=SubstrateClass.NERVE_APLASIA.value,
        age_years=3.0,
    )
    assert plan.recommendation is DeviceRecommendation.DEFER_PENDING_V11
    assert plan.t_level_initial_cl is None


def test_sgn_absent_nerve_present_defers_to_v09() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=SubstrateClass.SGN_ABSENT_NERVE_PRESENT.value,
        age_years=3.0,
    )
    assert plan.recommendation is DeviceRecommendation.DEFER_PENDING_V09


def test_indeterminate_defers_human_review() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=SubstrateClass.INDETERMINATE.value,
        age_years=3.0,
    )
    assert plan.recommendation is DeviceRecommendation.DEFER_HUMAN_REVIEW


def test_missing_substrate_decision_defers() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw=None,
        age_years=3.0,
    )
    assert plan.recommendation is DeviceRecommendation.DEFER_HUMAN_REVIEW


def test_unknown_substrate_class_defers() -> None:
    plan = ConventionalDeviceActor._plan(
        substrate_class_raw="some_garbage_class",
        age_years=3.0,
    )
    assert plan.recommendation is DeviceRecommendation.DEFER_HUMAN_REVIEW


def test_compute_threads_state() -> None:
    state = {
        "substrate_decision": {
            "substrate_class": SubstrateClass.SGN_PRESENT_HC_LOSS.value,
            "downstream_vertices": [],
            "confidence": "high",
            "rationale": "test",
        },
        "phenotype": {"age_years": 1.5},
    }
    delta = ConventionalDeviceActor.compute(state)
    assert delta["device_plan"]["recommendation"] == "electrical_ci"
    assert delta["requires_human_review"] is True
