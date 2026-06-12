"""V05 CmvTorchActor tests."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.cmv_torch import (
    CmvClassification,
    CmvTorchActor,
    CmvTorchInput,
    CmvTorchResult,
    IgGAvidity,
    PcrResult,
    SerologyResult,
    TorchAgent,
    TorchSerology,
)


def test_pcr_positive_within_window_confirmed() -> None:
    parsed = CmvTorchInput(
        sample_age_days=10,
        cmv_pcr_dbs=PcrResult.POSITIVE,
    )
    result = CmvTorchActor._classify(parsed)
    assert result.cmv_classification is CmvClassification.CONGENITAL_CMV_CONFIRMED
    assert result.cmv_positive is True


def test_pcr_positive_outside_window_inconclusive() -> None:
    parsed = CmvTorchInput(
        sample_age_days=60,
        cmv_pcr_dbs=PcrResult.POSITIVE,
    )
    result = CmvTorchActor._classify(parsed)
    # outside 21-day window → cannot confirm congenital
    assert result.cmv_classification is CmvClassification.NEGATIVE_OR_INCONCLUSIVE
    assert result.cmv_positive is False


def test_symptomatic_serology_probable() -> None:
    parsed = CmvTorchInput(
        clinically_symptomatic=True,
        cmv_igm=SerologyResult.POSITIVE,
        cmv_igg_avidity=IgGAvidity.LOW,
    )
    result = CmvTorchActor._classify(parsed)
    assert result.cmv_classification is CmvClassification.CONGENITAL_CMV_PROBABLE
    assert result.cmv_positive is True


def test_nothing_tested_not_tested_class() -> None:
    parsed = CmvTorchInput()
    result = CmvTorchActor._classify(parsed)
    assert result.cmv_classification is CmvClassification.NOT_TESTED
    assert result.cmv_positive is False


def test_torch_igm_positive_captured() -> None:
    parsed = CmvTorchInput(
        torch_serology=[
            TorchSerology(agent=TorchAgent.RUBELLA, igm=SerologyResult.POSITIVE),
            TorchSerology(agent=TorchAgent.TOXOPLASMA, igm=SerologyResult.NEGATIVE),
        ]
    )
    result = CmvTorchActor._classify(parsed)
    assert result.torch_positive_agents == [TorchAgent.RUBELLA]
    assert "rubella" in result.rationale.lower()


def test_compute_emits_substrate_evidence_delta() -> None:
    state = {
        "cmv_torch_input": {
            "sample_age_days": 5,
            "cmv_pcr_urine": "positive",
        },
        "substrate_evidence": {"cn_fiber_count": 3},
    }
    delta = CmvTorchActor.compute(state)
    assert delta["substrate_evidence"]["cmv_positive"] is True
    assert delta["substrate_evidence"]["cn_fiber_count"] == 3
    assert delta["requires_human_review"] is True


def test_compute_no_input_emits_empty_result() -> None:
    delta = CmvTorchActor.compute({})
    assert delta["cmv_torch_result"]["cmv_classification"] == "not_tested"
    assert delta["cmv_torch_result"]["cmv_positive"] is False
