import pytest

from kotodama.projects.uhl_right_neural.actors.trial_design import (
    TrialDesignActor,
    TrialDesignType,
    TrialPhase,
)

@pytest.fixture
def actor():
    return TrialDesignActor()

def test_trial_design_otof(actor):
    state = {"otof_tx_plan": {"access_tier": "otarmeni_tier_1_pmda"}}
    res = actor.compute(state)
    protocol = res.get("trial_protocol", {})
    assert protocol["phase"] == TrialPhase.PHASE_1_2A.value
    assert protocol["design_type"] == TrialDesignType.ADAPTIVE_SINGLE_ARM.value
    assert protocol["estimated_n"] == 12
    assert protocol["requires_human_review"] is True

def test_trial_design_device(actor):
    state = {"device_plan": {"recommendation": "cochlear_implant"}}
    res = actor.compute(state)
    protocol = res.get("trial_protocol", {})
    assert protocol["phase"] == TrialPhase.POST_MARKET_REGISTRY.value
    assert protocol["design_type"] == TrialDesignType.OPEN_LABEL_OBSERVATIONAL.value
    assert protocol["estimated_n"] == 100
    assert protocol["unilateral_specific"] is True

def test_trial_design_abi(actor):
    state = {"abi_plan": {"recommendation": "proceed_with_abi"}}
    res = actor.compute(state)
    protocol = res.get("trial_protocol", {})
    assert protocol["phase"] == TrialPhase.POST_MARKET_REGISTRY.value
    assert protocol["estimated_n"] == 50

def test_trial_design_neurotrophin(actor):
    state = {"neurotrophin_plan": {"dosing": "100ul"}}
    res = actor.compute(state)
    protocol = res.get("trial_protocol", {})
    assert protocol["phase"] == TrialPhase.PHASE_1_2A.value
    assert protocol["design_type"] == TrialDesignType.BAYESIAN_FUTILITY.value
    assert protocol["estimated_n"] == 15
