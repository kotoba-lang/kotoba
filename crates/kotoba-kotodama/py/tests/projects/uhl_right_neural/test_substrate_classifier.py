"""V06 SubstrateClassifierActor — 5-rule cascade tests.

Coverage maps 1:1 to the DMN table in
src/kotodama/projects/uhl_right_neural/dmn/substrate_classifier.md.
"""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.actors.substrate_classifier import (
    SubstrateClass,
    SubstrateClassifierActor,
    SubstrateEvidence,
)


@pytest.mark.parametrize(
    "evidence,expected_class,expected_confidence",
    [
        # Rule 1 — nerve aplasia takes absolute priority
        (
            SubstrateEvidence(
                cn_fiber_count=0,
                eabr_present=True,
                dpoae_present=True,
            ),
            SubstrateClass.NERVE_APLASIA,
            "high",
        ),
        # Rule 2 — SGN absent, nerve present
        (
            SubstrateEvidence(
                cn_fiber_count=1,
                eabr_present=False,
            ),
            SubstrateClass.SGN_ABSENT_NERVE_PRESENT,
            "medium",
        ),
        (
            SubstrateEvidence(
                cn_fiber_count=2,
                eabr_present=False,
            ),
            SubstrateClass.SGN_ABSENT_NERVE_PRESENT,
            "medium",
        ),
        # Rule 3 — SGN degenerating, nerve present
        (
            SubstrateEvidence(
                cn_fiber_count=3,
                eabr_present=True,
                eabr_latency_prolonged=True,
            ),
            SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT,
            "medium",
        ),
        # Rule 4 — SGN present, hair-cell loss only
        (
            SubstrateEvidence(
                cn_fiber_count=4,
                eabr_present=True,
                eabr_latency_prolonged=False,
                dpoae_present=False,
            ),
            SubstrateClass.SGN_PRESENT_HC_LOSS,
            "high",
        ),
        # Rule 5 — indeterminate (no evidence)
        (
            SubstrateEvidence(),
            SubstrateClass.INDETERMINATE,
            "low",
        ),
        # Rule 5 — partial / ambiguous evidence (eABR present, no other signals)
        (
            SubstrateEvidence(eabr_present=True),
            SubstrateClass.INDETERMINATE,
            "low",
        ),
    ],
)
def test_classification_rules(
    evidence: SubstrateEvidence,
    expected_class: SubstrateClass,
    expected_confidence: str,
) -> None:
    decision = SubstrateClassifierActor._classify(evidence)
    assert decision.substrate_class is expected_class
    assert decision.confidence == expected_confidence


def test_rule_1_dominates_other_signals() -> None:
    """nerve_aplasia must win even when other signals look 'good'."""
    ev = SubstrateEvidence(
        cn_fiber_count=0,
        eabr_present=True,
        eabr_latency_prolonged=False,
        dpoae_present=True,
    )
    decision = SubstrateClassifierActor._classify(ev)
    assert decision.substrate_class is SubstrateClass.NERVE_APLASIA


def test_compute_returns_state_delta() -> None:
    state = {
        "substrate_evidence": {"cn_fiber_count": 0},
    }
    out = SubstrateClassifierActor.compute(state)
    assert "substrate_decision" in out
    assert out["substrate_decision"]["substrate_class"] == "nerve_aplasia"
    assert out["requires_human_review"] is True


def test_compute_indeterminate_for_empty_evidence() -> None:
    out = SubstrateClassifierActor.compute({"substrate_evidence": {}})
    assert out["substrate_decision"]["substrate_class"] == "indeterminate"
    assert out["substrate_decision"]["downstream_vertices"] == []


def test_downstream_vertices_match_branch() -> None:
    cases = [
        (SubstrateClass.NERVE_APLASIA, ["V11_abi"]),
        (
            SubstrateClass.SGN_ABSENT_NERVE_PRESENT,
            ["V09_reprogramming", "V10_opto_ci"],
        ),
        (
            SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT,
            ["V08_neurotrophin", "V10_eci"],
        ),
        (
            SubstrateClass.SGN_PRESENT_HC_LOSS,
            ["V07_otof_tx_if_dfnb9", "V10_eci"],
        ),
    ]
    for klass, expected in cases:
        if klass is SubstrateClass.NERVE_APLASIA:
            ev = SubstrateEvidence(cn_fiber_count=0)
        elif klass is SubstrateClass.SGN_ABSENT_NERVE_PRESENT:
            ev = SubstrateEvidence(cn_fiber_count=1, eabr_present=False)
        elif klass is SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT:
            ev = SubstrateEvidence(
                cn_fiber_count=3, eabr_present=True, eabr_latency_prolonged=True
            )
        else:
            ev = SubstrateEvidence(
                cn_fiber_count=4,
                eabr_present=True,
                eabr_latency_prolonged=False,
                dpoae_present=False,
            )
        decision = SubstrateClassifierActor._classify(ev)
        assert decision.downstream_vertices == expected
