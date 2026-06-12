"""RSI cost economy and bonsai pruning."""

from __future__ import annotations

import json
from pathlib import Path

import kotoba_murakumo as km
from kotoba_murakumo.rsi import (
    BonsaiPruneRule,
    MutationCost,
    MutationKind,
    RsiPolicy,
    RsiTokenLedger,
    SelfMutationProposal,
    evaluate_training_rsi,
)
from kotoba_murakumo.training import TrainConfig, TrainingExample, train_step_loop


def _proposal(**overrides) -> SelfMutationProposal:
    base = {
        "proposal_id": "rsi-001",
        "kind": MutationKind.CODE_PATCH,
        "target": "runtime/router",
        "summary": "improve routing policy",
        "expected_delta": 0.20,
        "cost": MutationCost(compute_tokens=10, storage_tokens=2, risk_tokens=3),
    }
    base.update(overrides)
    return SelfMutationProposal(**base)


def test_rsi_exports_present() -> None:
    assert km.RsiPolicy is RsiPolicy
    assert km.RsiTokenLedger is RsiTokenLedger
    assert km.BonsaiPruneRule is BonsaiPruneRule


def test_rsi_executes_when_tokens_and_roi_are_sufficient() -> None:
    ledger = RsiTokenLedger(balance=100)
    policy = RsiPolicy(min_roi=0.001, max_cost_tokens=50)
    decision = policy.decide(_proposal(), ledger)

    assert decision.action == "execute"
    assert decision.promoted is True
    assert decision.cost_tokens == 15
    assert decision.ledger_after.spent == 15
    assert decision.ledger_after.available == 85


def test_rsi_prunes_when_cost_exceeds_budget() -> None:
    ledger = RsiTokenLedger(balance=10)
    policy = RsiPolicy(min_roi=0.0, max_cost_tokens=50)
    decision = policy.decide(_proposal(), ledger)

    assert decision.action == "prune"
    assert decision.reason == "cost-exceeded"
    assert decision.ledger_after == ledger


def test_rsi_prunes_negative_roi_branch() -> None:
    ledger = RsiTokenLedger(balance=100)
    policy = RsiPolicy(min_roi=0.05, max_cost_tokens=50)
    decision = policy.decide(_proposal(expected_delta=0.01), ledger)

    assert decision.action == "prune"
    assert decision.reason == "negative-roi"


def test_human_bonsai_prune_rule_overrides_autonomy() -> None:
    ledger = RsiTokenLedger(balance=100)
    policy = RsiPolicy(
        min_roi=0.0,
        max_cost_tokens=50,
        prune_rules=(BonsaiPruneRule(rule_id="no-router", pattern="runtime/router"),),
    )
    decision = policy.decide(_proposal(), ledger)

    assert decision.action == "prune"
    assert decision.reason == "human-bonsai"
    assert decision.cost_tokens == 0


def test_training_result_can_be_evaluated_as_rsi_branch(tmp_path: Path) -> None:
    train_result = train_step_loop(
        config=TrainConfig(model_id="maxwell-1", run_id="rsi-train-001", steps=2),
        examples=[
            TrainingExample(prompt="good prompt", target="good target", quality=0.9),
            TrainingExample(prompt="second prompt", target="second target", quality=0.8),
        ],
        store_root=tmp_path,
    )

    decision = evaluate_training_rsi(
        train_result,
        store_root=tmp_path,
        ledger=RsiTokenLedger(balance=100),
        policy=RsiPolicy(min_roi=0.0001, max_cost_tokens=50),
        cost=MutationCost(compute_tokens=10, storage_tokens=2, risk_tokens=3),
    )

    assert decision.action == "execute"
    datoms = [
        json.loads(line)
        for line in (tmp_path / "datoms.ndjson").read_text().splitlines()
        if line
    ]
    assert any(d["graph"] == "rsi/mutations" for d in datoms)
    assert any(d["graph"] == "rsi/economy" for d in datoms)
    economy = next(d for d in datoms if d["graph"] == "rsi/economy")
    assert economy["object"]["ledger_after"]["spent"] == 15


def test_training_rsi_prune_persists_bonsai_branch(tmp_path: Path) -> None:
    train_result = train_step_loop(
        config=TrainConfig(model_id="maxwell-1", run_id="rsi-prune-001", steps=1),
        examples=[TrainingExample(prompt="good prompt", target="good target", quality=0.9)],
        store_root=tmp_path,
    )

    decision = evaluate_training_rsi(
        train_result,
        store_root=tmp_path,
        ledger=RsiTokenLedger(balance=100),
        policy=RsiPolicy(
            min_roi=0.0,
            max_cost_tokens=50,
            prune_rules=(BonsaiPruneRule(rule_id="prune-maxwell", pattern="maxwell-1"),),
        ),
        cost=MutationCost(compute_tokens=10),
    )

    assert decision.action == "prune"
    datoms = [
        json.loads(line)
        for line in (tmp_path / "datoms.ndjson").read_text().splitlines()
        if line
    ]
    pruning = [d for d in datoms if d["graph"] == "rsi/pruning"]
    assert len(pruning) == 1
    assert pruning[0]["predicate"] == "pruned/human-bonsai"
