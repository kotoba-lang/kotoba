"""Rule-fitness ledger + meta-reflector — the self-evolution loop scoring AND
pruning ITSELF.

Closes the meta-loop the bare Kaizen loop lacked. The observer emits proposals
and the PR-agent opens PRs, but nothing fed the *outcome* (was the PR merged or
rejected?) back into the loop. This module does:

  belief → observe → update → policy

  - Each rule carries a Beta(alpha, beta) belief over "do my proposals get
    ACCEPTED (merged)?". Prior Beta(1, 1) = uniform (no evidence → 0.5).
  - A PR outcome is an observation: merged → accept (+1 alpha), closed-unmerged
    → reject (+1 beta). This is a minimal active-inference belief update over a
    generative model of acceptance.
  - The posterior mean is the rule's FITNESS SCORE.
  - POLICY (pruning): a rule whose fitness falls below ``prune_below`` after at
    least ``min_samples`` observations is disabled, so the loop stops emitting
    proposals humans keep rejecting — the loop prunes itself.

Persistence is an append-friendly JSON snapshot next to the proposal queue
(same NDJSON-on-hostPath substrate the observer/pr-agent already share), so the
ledger survives pod restarts without a new backend.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("kotodama.organism.kaizen.fitness")


@dataclass
class RuleFitness:
    rule_id: str
    accepted: int = 0
    rejected: int = 0
    last_ts_ms: int = 0

    @property
    def samples(self) -> int:
        return self.accepted + self.rejected

    def posterior_mean(self, prior_a: float = 1.0, prior_b: float = 1.0) -> float:
        """Beta(accepted+prior_a, rejected+prior_b) mean = expected acceptance."""
        a = self.accepted + prior_a
        b = self.rejected + prior_b
        return a / (a + b)


class RuleFitnessLedger:
    """Per-rule Beta belief over proposal acceptance, persisted as JSON."""

    def __init__(self, path: Path | str, *, prior_a: float = 1.0, prior_b: float = 1.0):
        self.path = Path(path)
        self.prior_a = prior_a
        self.prior_b = prior_b
        self._stats: dict[str, RuleFitness] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text() or "{}")
        except json.JSONDecodeError:
            logger.warning("fitness ledger %s unreadable; starting fresh", self.path)
            return
        for rid, d in raw.get("rules", {}).items():
            self._stats[rid] = RuleFitness(
                rule_id=rid,
                accepted=int(d.get("accepted", 0)),
                rejected=int(d.get("rejected", 0)),
                last_ts_ms=int(d.get("lastTsMs", 0)),
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "v": 1,
            "rules": {
                rid: {
                    "accepted": s.accepted,
                    "rejected": s.rejected,
                    "lastTsMs": s.last_ts_ms,
                    "fitness": round(s.posterior_mean(self.prior_a, self.prior_b), 4),
                    "samples": s.samples,
                }
                for rid, s in self._stats.items()
            },
        }
        self.path.write_text(json.dumps(out, indent=2))

    def record_outcome(self, rule_id: str, accepted: bool, *, ts_ms: int | None = None) -> None:
        s = self._stats.setdefault(rule_id, RuleFitness(rule_id=rule_id))
        if accepted:
            s.accepted += 1
        else:
            s.rejected += 1
        s.last_ts_ms = ts_ms if ts_ms is not None else int(time.time() * 1000)
        self.save()

    def fitness(self, rule_id: str) -> float:
        s = self._stats.get(rule_id)
        if s is None:
            return RuleFitness(rule_id).posterior_mean(self.prior_a, self.prior_b)
        return s.posterior_mean(self.prior_a, self.prior_b)

    def samples(self, rule_id: str) -> int:
        s = self._stats.get(rule_id)
        return s.samples if s else 0

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            rid: {"fitness": round(s.posterior_mean(self.prior_a, self.prior_b), 4),
                  "samples": s.samples, "accepted": s.accepted, "rejected": s.rejected}
            for rid, s in self._stats.items()
        }


class MetaReflector:
    """Scores + prunes the loop itself from the rule-fitness ledger.

    ``disabled_rules()`` is the POLICY: rules with enough evidence whose expected
    acceptance is below ``prune_below`` are pruned (disabled). The KaizenObserver
    consults this to skip emitting from a rule that humans keep rejecting.
    """

    def __init__(
        self,
        ledger: RuleFitnessLedger,
        *,
        min_samples: int = 5,
        prune_below: float = 0.34,
    ):
        self.ledger = ledger
        self.min_samples = min_samples
        self.prune_below = prune_below

    def disabled_rules(self) -> set[str]:
        return {
            rid
            for rid, st in self.ledger.snapshot().items()
            if st["samples"] >= self.min_samples and st["fitness"] < self.prune_below
        }

    def record(self, rule_id: str, accepted: bool, *, ts_ms: int | None = None) -> None:
        self.ledger.record_outcome(rule_id, accepted, ts_ms=ts_ms)


# ── PR-outcome resolution ─────────────────────────────────────────────────

# A PR-state lookup: given a pending-outcome record, return one of
# "merged" | "closed" | "open" | "unknown".
PrStateFn = Callable[[dict[str, Any]], str]


def append_pending_outcome(outcomes_path: Path | str, *, rule_id: str, pr_url: str,
                           branch: str, ts_ms: int | None = None) -> None:
    """Append a {ruleId, prUrl, branch, status:pending} line — the PR-agent calls
    this when it opens a real PR so the outcome can be resolved later."""
    p = Path(outcomes_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ruleId": rule_id, "prUrl": pr_url, "branch": branch,
        "tsMs": ts_ms if ts_ms is not None else int(time.time() * 1000),
        "status": "pending",
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def resolve_outcomes(outcomes_path: Path | str, ledger: RuleFitnessLedger,
                     pr_state_fn: PrStateFn) -> dict[str, int]:
    """Resolve pending PR outcomes into the fitness ledger.

    For each pending record, ``pr_state_fn`` returns the PR state. merged →
    accept, closed (unmerged) → reject; both are recorded and dropped from the
    pending file. open/unknown stay pending. Returns counts.
    """
    p = Path(outcomes_path)
    if not p.exists():
        return {"resolved": 0, "accepted": 0, "rejected": 0, "pending": 0}
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    still_pending: list[str] = []
    accepted = rejected = 0
    for ln in lines:
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        state = pr_state_fn(rec)
        if state == "merged":
            ledger.record_outcome(rec["ruleId"], True)
            accepted += 1
        elif state == "closed":
            ledger.record_outcome(rec["ruleId"], False)
            rejected += 1
        else:  # open / unknown → keep pending
            still_pending.append(ln)
    p.write_text(("\n".join(still_pending) + "\n") if still_pending else "")
    return {"resolved": accepted + rejected, "accepted": accepted,
            "rejected": rejected, "pending": len(still_pending)}


__all__ = [
    "RuleFitness",
    "RuleFitnessLedger",
    "MetaReflector",
    "append_pending_outcome",
    "resolve_outcomes",
    "PrStateFn",
]
