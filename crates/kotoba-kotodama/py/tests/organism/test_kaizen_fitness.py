"""Meta self-reflection: rule-fitness scoring + pruning + PR-outcome learning.

Closes the meta-loop — the loop scores and prunes ITSELF from PR outcomes.
"""

from __future__ import annotations

from pathlib import Path

from kotodama.organism.kaizen import KaizenObserver, Observation, ShardHealthz
from kotodama.organism.kaizen.fitness import (
    RuleFitnessLedger,
    MetaReflector,
    append_pending_outcome,
    resolve_outcomes,
)


def test_ledger_beta_posterior_and_persistence(tmp_path: Path):
    led = RuleFitnessLedger(tmp_path / "fit.json")
    # No evidence → uniform prior mean 0.5
    assert led.fitness("r") == 0.5
    # 4 accept / 1 reject → Beta(5,2) mean = 5/7
    for _ in range(4):
        led.record_outcome("r", True)
    led.record_outcome("r", False)
    assert abs(led.fitness("r") - 5 / 7) < 1e-9
    assert led.samples("r") == 5
    # Persisted + reloaded
    led2 = RuleFitnessLedger(tmp_path / "fit.json")
    assert led2.samples("r") == 5
    assert abs(led2.fitness("r") - 5 / 7) < 1e-9


def test_reflector_prunes_only_with_enough_evidence(tmp_path: Path):
    led = RuleFitnessLedger(tmp_path / "fit.json")
    refl = MetaReflector(led, min_samples=5, prune_below=0.34)
    # 1 reject — below threshold count → NOT pruned (insufficient evidence)
    led.record_outcome("bad", False)
    assert refl.disabled_rules() == set()
    # 5 rejects total → Beta(1,6) mean ≈ 0.143 < 0.34 AND samples>=5 → pruned
    for _ in range(4):
        led.record_outcome("bad", False)
    assert "bad" in refl.disabled_rules()
    # a mostly-accepted rule with enough samples is NOT pruned
    for _ in range(6):
        led.record_outcome("good", True)
    assert "good" not in refl.disabled_rules()


def _saturating_obs() -> Observation:
    # warm == capacity AND owned > capacity → triggers lru-saturation rule
    return Observation(
        ts=0,
        shards=[ShardHealthz(shard=0, reachable=True, warm_count=4096,
                             warm_capacity=4096, owned_count=9000)],
    )


def test_observer_skips_pruned_rule(tmp_path: Path):
    obs = _saturating_obs()
    # Baseline: lru-saturation fires.
    base = KaizenObserver(shard_urls=[], queue_paths=[], proposal_path=tmp_path / "p.ndjson")
    assert any(p.rule_id == "lru-saturation" for p in base.run_rules(obs))

    # With a reflector that has pruned lru-saturation, the observer skips it.
    led = RuleFitnessLedger(tmp_path / "fit.json")
    for _ in range(6):
        led.record_outcome("lru-saturation", False)  # humans kept rejecting it
    refl = MetaReflector(led, min_samples=5, prune_below=0.34)
    assert "lru-saturation" in refl.disabled_rules()
    obsvr = KaizenObserver(shard_urls=[], queue_paths=[], proposal_path=tmp_path / "p2.ndjson",
                           meta_reflector=refl)
    assert not any(p.rule_id == "lru-saturation" for p in obsvr.run_rules(obs))


def test_resolve_outcomes_updates_ledger(tmp_path: Path):
    outcomes = tmp_path / "observer.outcomes.ndjson"
    append_pending_outcome(outcomes, rule_id="sweep-latency-p95", pr_url="u/1", branch="b1")
    append_pending_outcome(outcomes, rule_id="sweep-latency-p95", pr_url="u/2", branch="b2")
    append_pending_outcome(outcomes, rule_id="mood-concentration", pr_url="u/3", branch="b3")

    # merged → accept; closed → reject; open → stays pending
    states = {"u/1": "merged", "u/2": "closed", "u/3": "open"}
    led = RuleFitnessLedger(tmp_path / "fit.json")
    res = resolve_outcomes(outcomes, led, lambda rec: states[rec["prUrl"]])

    assert res == {"resolved": 2, "accepted": 1, "rejected": 1, "pending": 1}
    assert led.samples("sweep-latency-p95") == 2  # 1 accept + 1 reject
    # the open one stays pending in the file
    assert "u/3" in outcomes.read_text()
    assert "u/1" not in outcomes.read_text()


def test_full_meta_loop_prunes_a_rejected_rule(tmp_path: Path):
    """End-to-end meta-loop: a rule whose PRs are all rejected gets pruned, so
    the observer stops emitting it."""
    led = RuleFitnessLedger(tmp_path / "fit.json")
    refl = MetaReflector(led, min_samples=5, prune_below=0.34)
    outcomes = tmp_path / "observer.outcomes.ndjson"
    # Simulate 5 lru-saturation PRs that all got rejected by humans.
    for i in range(5):
        append_pending_outcome(outcomes, rule_id="lru-saturation", pr_url=f"u/{i}", branch=f"b{i}")
    resolve_outcomes(outcomes, led, lambda rec: "closed")  # all rejected

    obsvr = KaizenObserver(shard_urls=[], queue_paths=[], proposal_path=tmp_path / "p.ndjson",
                           meta_reflector=refl)
    fired = {p.rule_id for p in obsvr.run_rules(_saturating_obs())}
    assert "lru-saturation" not in fired  # pruned by its own rejected-PR history
