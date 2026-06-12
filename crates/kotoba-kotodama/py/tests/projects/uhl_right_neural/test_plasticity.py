"""V12 PlasticityActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.plasticity import (
    OutcomeCeiling,
    PhaseGate,
    PlasticityActor,
)


@pytest.mark.parametrize(
    "age,expected_phase,expected_ceiling,gate_passed",
    [
        (0.5, PhaseGate.OPTIMAL, OutcomeCeiling.HIGH, True),
        (3.0, PhaseGate.OPTIMAL, OutcomeCeiling.HIGH, True),
        (4.0, PhaseGate.REDUCED, OutcomeCeiling.MODERATE, True),
        (6.99, PhaseGate.REDUCED, OutcomeCeiling.MODERATE, True),
        (7.0, PhaseGate.MARGINAL, OutcomeCeiling.LIMITED, False),
        (11.99, PhaseGate.MARGINAL, OutcomeCeiling.LIMITED, False),
        (12.0, PhaseGate.CLOSED, OutcomeCeiling.LATE_ADULT, False),
        (45.0, PhaseGate.CLOSED, OutcomeCeiling.LATE_ADULT, False),
    ],
)
def test_age_window_phase_gate(
    age: float,
    expected_phase: PhaseGate,
    expected_ceiling: OutcomeCeiling,
    gate_passed: bool,
) -> None:
    plan = PlasticityActor._gate(age_years=age, cmv_positive=False)
    assert plan.phase_gate is expected_phase
    assert plan.outcome_ceiling is expected_ceiling
    assert plan.phase_gate_passed is gate_passed


def test_cmv_positive_adds_surveillance_note() -> None:
    plan = PlasticityActor._gate(age_years=2.0, cmv_positive=True)
    assert any("CMV" in n for n in plan.notes)
    # but doesn't change phase gate
    assert plan.phase_gate is PhaseGate.OPTIMAL


def test_compute_without_phenotype_emits_absent_marker() -> None:
    delta = PlasticityActor.compute({})
    assert delta["plasticity_plan"]["_absent"] is True


def test_compute_reads_age_and_cmv_flag() -> None:
    state = {
        "phenotype": {"age_years": 5.0},
        "substrate_evidence": {"cmv_positive": True},
    }
    delta = PlasticityActor.compute(state)
    assert delta["plasticity_plan"]["phase_gate"] == "reduced"
    assert delta["plasticity_plan"]["phase_gate_passed"] is True
    assert any("CMV" in n for n in delta["plasticity_plan"]["notes"])
    assert delta["requires_human_review"] is True
