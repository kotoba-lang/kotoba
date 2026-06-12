"""Cost-bounded autonomous self-modification policy.

The system is allowed to propose and execute self-modifying work, but every
mutation consumes a scarce token budget and remains pruneable. This is the
Bitcoin-like constraint requested for RSI: autonomy is permitted; unbounded
growth is not free.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from .training import KotobaArtifactStore, TrainRunResult


class MutationKind(StrEnum):
    TRAIN = "train"
    CODE_PATCH = "code-patch"
    DATASET_EXPANSION = "dataset-expansion"
    HYPERPARAMETER_SEARCH = "hyperparameter-search"
    DEPLOYMENT_FLIP = "deployment-flip"


class PruneReason(StrEnum):
    COST_EXCEEDED = "cost-exceeded"
    NEGATIVE_ROI = "negative-roi"
    HUMAN_BONSAI = "human-bonsai"
    POLICY_FLOOR = "policy-floor"
    STALE_BRANCH = "stale-branch"


@dataclass(frozen=True, slots=True)
class RsiTokenLedger:
    """Scarce improvement budget.

    ``balance`` is intentionally integer-denominated. The runtime may act
    autonomously while it has tokens, but cannot mint unlimited improvement work
    without a separate funding event recorded in the ledger.
    """

    balance: int
    reserved: int = 0
    spent: int = 0

    @property
    def available(self) -> int:
        return max(0, self.balance - self.reserved - self.spent)

    def debit(self, amount: int) -> "RsiTokenLedger":
        if amount < 0:
            raise ValueError("amount must be >= 0")
        if amount > self.available:
            raise ValueError(f"insufficient RSI tokens: need={amount} available={self.available}")
        return RsiTokenLedger(
            balance=self.balance,
            reserved=self.reserved,
            spent=self.spent + amount,
        )


@dataclass(frozen=True, slots=True)
class MutationCost:
    """Cost model for one self-modifying branch."""

    compute_tokens: int = 0
    storage_tokens: int = 0
    risk_tokens: int = 0
    review_tokens: int = 0

    @property
    def total(self) -> int:
        return self.compute_tokens + self.storage_tokens + self.risk_tokens + self.review_tokens


@dataclass(frozen=True, slots=True)
class SelfMutationProposal:
    """One autonomous self-modification candidate."""

    proposal_id: str
    kind: MutationKind
    target: str
    summary: str
    expected_delta: float
    cost: MutationCost
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BonsaiPruneRule:
    """Human / operator pruning rule."""

    rule_id: str
    pattern: str
    reason: PruneReason = PruneReason.HUMAN_BONSAI
    active: bool = True

    def matches(self, proposal: SelfMutationProposal) -> bool:
        if not self.active:
            return False
        haystack = " ".join(
            [
                proposal.proposal_id,
                proposal.target,
                proposal.summary,
                proposal.kind.value,
                json.dumps(proposal.metadata, sort_keys=True),
            ]
        )
        return self.pattern in haystack


@dataclass(frozen=True, slots=True)
class RsiDecision:
    """Decision for one self-modification proposal."""

    proposal_id: str
    action: Literal["execute", "prune"]
    reason: str
    cost_tokens: int
    ledger_after: RsiTokenLedger
    roi: float
    promoted: bool


@dataclass(frozen=True, slots=True)
class RsiPolicy:
    """Autonomy constraints for RSI."""

    min_roi: float = 0.0
    max_cost_tokens: int = 10_000
    prune_rules: tuple[BonsaiPruneRule, ...] = ()

    def decide(self, proposal: SelfMutationProposal, ledger: RsiTokenLedger) -> RsiDecision:
        for rule in self.prune_rules:
            if rule.matches(proposal):
                return RsiDecision(
                    proposal_id=proposal.proposal_id,
                    action="prune",
                    reason=rule.reason.value,
                    cost_tokens=0,
                    ledger_after=ledger,
                    roi=0.0,
                    promoted=False,
                )

        cost = proposal.cost.total
        if cost > self.max_cost_tokens:
            return RsiDecision(
                proposal_id=proposal.proposal_id,
                action="prune",
                reason=PruneReason.COST_EXCEEDED.value,
                cost_tokens=cost,
                ledger_after=ledger,
                roi=0.0,
                promoted=False,
            )
        if cost > ledger.available:
            return RsiDecision(
                proposal_id=proposal.proposal_id,
                action="prune",
                reason=PruneReason.COST_EXCEEDED.value,
                cost_tokens=cost,
                ledger_after=ledger,
                roi=0.0,
                promoted=False,
            )

        roi = proposal.expected_delta / max(1, cost)
        if roi < self.min_roi:
            return RsiDecision(
                proposal_id=proposal.proposal_id,
                action="prune",
                reason=PruneReason.NEGATIVE_ROI.value,
                cost_tokens=cost,
                ledger_after=ledger,
                roi=roi,
                promoted=False,
            )

        return RsiDecision(
            proposal_id=proposal.proposal_id,
            action="execute",
            reason="cost-bounded-autonomous-execute",
            cost_tokens=cost,
            ledger_after=ledger.debit(cost),
            roi=roi,
            promoted=True,
        )


def proposal_from_training_result(
    result: TrainRunResult,
    *,
    cost: MutationCost,
    target: str = "llm/default-weight",
) -> SelfMutationProposal:
    """Convert a train result into an RSI self-mutation candidate."""
    return SelfMutationProposal(
        proposal_id=f"rsi-train-{result.run_id}",
        kind=MutationKind.TRAIN,
        target=target,
        summary=f"Promote trained checkpoint for {result.model_id}",
        expected_delta=result.bench_delta,
        cost=cost,
        metadata={
            "model_id": result.model_id,
            "run_id": result.run_id,
            "final_weight_cid": result.final_weight_cid,
            "checkpoint_cids": list(result.checkpoint_cids),
            "training_promoted": result.promoted,
            "selected_examples": result.selected_examples,
            "rejected_examples": result.rejected_examples,
        },
    )


def persist_rsi_decision(
    store: KotobaArtifactStore,
    *,
    proposal: SelfMutationProposal,
    decision: RsiDecision,
    tx: str,
) -> None:
    """Persist proposal + decision to the Kotoba artifact projection."""
    store.append_datom(
        graph="rsi/mutations",
        subject=proposal.proposal_id,
        predicate=f"mutation/{proposal.kind.value}",
        obj=asdict(proposal),
        tx=tx,
    )
    store.append_datom(
        graph="rsi/economy",
        subject=proposal.proposal_id,
        predicate="decision",
        obj=asdict(decision),
        tx=tx,
    )
    if decision.action == "prune":
        store.append_datom(
            graph="rsi/pruning",
            subject=proposal.proposal_id,
            predicate=f"pruned/{decision.reason}",
            obj=asdict(decision),
            tx=tx,
        )


def evaluate_training_rsi(
    result: TrainRunResult,
    *,
    store_root: Path | str,
    ledger: RsiTokenLedger,
    policy: RsiPolicy,
    cost: MutationCost,
) -> RsiDecision:
    """Evaluate a train run as an autonomous self-modification branch."""
    store = KotobaArtifactStore(store_root)
    proposal = proposal_from_training_result(result, cost=cost)
    decision = policy.decide(proposal, ledger)
    persist_rsi_decision(store, proposal=proposal, decision=decision, tx=result.run_id)
    return decision


__all__ = [
    "BonsaiPruneRule",
    "MutationCost",
    "MutationKind",
    "PruneReason",
    "RsiDecision",
    "RsiPolicy",
    "RsiTokenLedger",
    "SelfMutationProposal",
    "evaluate_training_rsi",
    "persist_rsi_decision",
    "proposal_from_training_result",
]
