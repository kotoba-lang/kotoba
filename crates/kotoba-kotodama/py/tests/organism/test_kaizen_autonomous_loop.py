"""Autonomous Observer → PR-agent loop (no human in the hint translation).

Regression guard for the gap surfaced 2026-06-08: the built-in performance
rules (`sweep-latency-p95`, `lru-saturation`) used to emit a human-readable
``patch_hint`` ("env LRU_MAX → next power-of-two up") that the Kaizen PR agent
could not apply, so an Observer proposal silently produced zero modified files
and never became a PR. The rules now emit the auto-applicable ``'old' -> 'new'``
form, so Observer.run_rules → KaizenPrAgent.consume_one applies a real patch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from kotodama.organism.kaizen import (
    KaizenObserver,
    Observation,
    ShardHealthz,
)
from kotodama.organism.kaizen.pr_agent import KaizenPrAgent


def _seed_repo(tmp_path: Path, shard: int, lru_value: int) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    tgt = repo / f"50-infra/k8s/unispsc-organism-fleet/shard-{shard}/daemonset.yaml"
    tgt.parent.mkdir(parents=True)
    tgt.write_text(
        "        - name: UNISPSC_ORGANISM_LRU_MAX\n"
        f'          value: "{lru_value}"\n'
    )
    return repo


def test_sweep_latency_rule_emits_auto_applicable_hint():
    obs = Observation(
        ts=1_700_000_000_000,
        shards=[ShardHealthz(shard=1, reachable=True, owned_count=8541,
                             warm_count=4096, warm_capacity=4096,
                             last_tick_duration_ms=8200.0)],
        history={1: [8000.0, 8100.0, 8200.0, 8300.0, 8150.0, 8250.0, 8400.0]},
    )
    observer = KaizenObserver(shard_urls=[], queue_paths=[], proposal_path=Path("/dev/null"))
    proposals = observer.run_rules(obs)
    by_rule = {p.rule_id: p for p in proposals}

    # sweep-latency: 4096 → next power of two up = 8192
    sweep = by_rule["sweep-latency-p95"]
    assert sweep.suggested_action is not None
    assert sweep.suggested_action.patch_hint == "'value: \"4096\"' -> 'value: \"8192\"'"

    # lru-saturation: next power of two >= owned_count(8541) = 16384
    lru = by_rule["lru-saturation"]
    assert lru.suggested_action.patch_hint == "'value: \"4096\"' -> 'value: \"16384\"'"


def test_observer_proposal_flows_to_pr_agent_patch(tmp_path: Path):
    """End-to-end: Observer proposal → PR agent applies the patch for real.

    subprocess.run (git/gh) is mocked to a no-op; subprocess.check_output
    (current branch) returns "main". _apply_patch performs real file I/O, so
    we assert the daemonset value was bumped autonomously.
    """
    obs = Observation(
        ts=1_700_000_000_000,
        shards=[ShardHealthz(shard=1, reachable=True, owned_count=8541,
                             warm_count=4096, warm_capacity=4096,
                             last_tick_duration_ms=8200.0)],
        history={1: [8000.0, 8100.0, 8200.0, 8300.0, 8150.0, 8250.0, 8400.0]},
    )
    observer = KaizenObserver(shard_urls=[], queue_paths=[], proposal_path=Path("/dev/null"))
    sweep = {p.rule_id: p for p in observer.run_rules(obs)}["sweep-latency-p95"]

    queue = tmp_path / "observer.ndjson"
    queue.write_text(json.dumps(sweep.to_ndjson_dict(ts_ms=obs.ts)) + "\n")

    repo = _seed_repo(tmp_path, shard=1, lru_value=4096)
    tgt = repo / "50-infra/k8s/unispsc-organism-fleet/shard-1/daemonset.yaml"

    with patch("subprocess.check_output", return_value="main\n"), \
         patch("subprocess.run", return_value=MagicMock(
             check_returncode=lambda: None, stdout="Dry run successful.")):
        agent = KaizenPrAgent(queue, repo, dry_run=True)
        result = agent.consume_one()

    # The PR agent applied the real patch + reported a (dry-run) success.
    assert result == "Dry run successful."
    assert 'value: "8192"' in tgt.read_text()
    assert 'value: "4096"' not in tgt.read_text()
    # Queue drained.
    assert queue.read_text().strip() == ""


def test_structured_edit_targets_named_var_not_first_occurrence(tmp_path: Path):
    """The structured env-set edit bumps LRU_MAX even when another env var
    shares the same value — proving it targets the named var, not the first
    `value: "4096"` occurrence in the file."""
    obs = Observation(
        ts=1_700_000_000_000,
        shards=[ShardHealthz(shard=2, reachable=True, owned_count=8541,
                             warm_count=4096, warm_capacity=4096,
                             last_tick_duration_ms=8200.0)],
        history={2: [8200.0] * 8},
    )
    observer = KaizenObserver(shard_urls=[], queue_paths=[], proposal_path=Path("/dev/null"))
    sweep = {p.rule_id: p for p in observer.run_rules(obs)}["sweep-latency-p95"]
    assert sweep.suggested_action.patch_edits  # structured edit present

    repo = tmp_path / "repo"
    repo.mkdir()
    tgt = repo / "50-infra/k8s/unispsc-organism-fleet/shard-2/daemonset.yaml"
    tgt.parent.mkdir(parents=True)
    # TWO env vars share value "4096"; only LRU_MAX must change.
    tgt.write_text(
        "        - name: UNISPSC_ORGANISM_TICK_BUDGET\n"
        '          value: "4096"\n'
        "        - name: UNISPSC_ORGANISM_LRU_MAX\n"
        '          value: "4096"\n'
    )
    queue = tmp_path / "observer.ndjson"
    queue.write_text(json.dumps(sweep.to_ndjson_dict(ts_ms=obs.ts)) + "\n")

    with patch("subprocess.check_output", return_value="main\n"), \
         patch("subprocess.run", return_value=MagicMock(
             check_returncode=lambda: None, stdout="Dry run successful.")):
        agent = KaizenPrAgent(queue, repo, dry_run=True)
        result = agent.consume_one()

    assert result == "Dry run successful."
    out = tgt.read_text()
    # LRU_MAX bumped to 8192; the unrelated TICK_BUDGET value untouched.
    assert 'name: UNISPSC_ORGANISM_LRU_MAX\n          value: "8192"' in out
    assert 'name: UNISPSC_ORGANISM_TICK_BUDGET\n          value: "4096"' in out
