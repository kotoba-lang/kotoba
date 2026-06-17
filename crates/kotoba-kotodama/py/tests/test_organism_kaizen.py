"""Tests for kotodama.organism.kaizen (ADR-2605240200)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotodama.organism.kaizen import (
    PROPOSAL_SCHEMA_VERSION,
    RULE_REGISTRY,
    ErrorRateRule,
    FleetUnreachableRule,
    KaizenObserver,
    KaizenProposal,
    LruSaturationRule,
    MoodConcentrationRule,
    Observation,
    PostThroughputStalledRule,
    PrAgentHint,
    QueueSample,
    ShardHealthz,
    SuggestedAction,
    SweepLatencyP95Rule,
    sample_queue,
)


# ── Registry has all six built-in rules ───────────────────────────────


def test_six_built_in_rules_registered():
    expected = {
        "sweep-latency-p95",
        "lru-saturation",
        "error-rate",
        "post-throughput-stalled",
        "mood-concentration",
        "fleet-unreachable",
    }
    assert expected <= set(RULE_REGISTRY.keys())


# ── Individual rules ──────────────────────────────────────────────────


def test_sweep_latency_under_threshold_no_proposal():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=0, reachable=True, last_tick_duration_ms=500.0)],
        history={0: [500.0] * 30},
    )
    assert SweepLatencyP95Rule()(obs) == []


def test_sweep_latency_p95_over_threshold_fires_warn():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=1, reachable=True, last_tick_duration_ms=8000.0, owned_count=8541, warm_count=4096, warm_capacity=4096)],
        history={1: [8200.0] * 24},
    )
    proposals = SweepLatencyP95Rule()(obs)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.rule_id == "sweep-latency-p95"
    assert p.severity == "critical"  # > 5000
    assert p.actor_scope == "shard:1"
    assert "shard-1" in p.summary
    assert p.suggested_action is not None
    assert p.suggested_action.kind == "config-change"
    assert any("shard-1" in tf for tf in p.suggested_action.target_files)


def test_sweep_latency_warns_at_intermediate():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=0, reachable=True, last_tick_duration_ms=2000.0)],
        history={0: [2000.0] * 24},
    )
    proposals = SweepLatencyP95Rule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "warn"


def test_lru_saturation_fires_when_at_capacity():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=0, reachable=True, warm_count=4096, warm_capacity=4096, owned_count=4597)],
    )
    proposals = LruSaturationRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "warn"
    assert proposals[0].suggested_action is not None
    # Auto-applicable hint: bump LRU_MAX to the next power of two that holds
    # all owned codes (>= 4597 → 8192), in the PR-agent's 'old' -> 'new' form.
    assert proposals[0].suggested_action.patch_hint == "'value: \"4096\"' -> 'value: \"8192\"'"


def test_lru_saturation_no_fire_when_owned_fits():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=0, reachable=True, warm_count=2000, warm_capacity=4096, owned_count=2000)],
    )
    assert LruSaturationRule()(obs) == []


def test_error_rate_critical_above_10pct():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=2, reachable=True, total_classifications=900, total_errors=150)],
    )
    proposals = ErrorRateRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "critical"


def test_error_rate_warn_between_1_and_10pct():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=2, reachable=True, total_classifications=950, total_errors=50)],
    )
    proposals = ErrorRateRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "warn"


def test_error_rate_no_fire_when_volume_too_low():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=2, reachable=True, total_classifications=50, total_errors=20)],
    )
    assert ErrorRateRule()(obs) == []


def test_post_throughput_stalled_after_12_ticks():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=1, reachable=True, tick_count=20, total_posts=0)],
    )
    proposals = PostThroughputStalledRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "warn"
    assert proposals[0].suggested_action.kind == "code-change"


def test_post_throughput_warmup_skipped():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=1, reachable=True, tick_count=5, total_posts=0)],
    )
    assert PostThroughputStalledRule()(obs) == []


def test_mood_concentration_fires_above_80pct():
    obs = Observation(
        ts=0,
        shards=[],
        queues=[
            QueueSample(
                shard=0,
                sample_count=1000,
                mood_distribution={"neutral": 850, "joyful": 100, "calm": 50},
            )
        ],
    )
    proposals = MoodConcentrationRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "info"
    assert "85%" in proposals[0].summary
    assert "neutral" in proposals[0].summary


def test_mood_concentration_under_80pct_no_fire():
    obs = Observation(
        ts=0,
        shards=[],
        queues=[
            QueueSample(
                shard=0,
                sample_count=1000,
                mood_distribution={"neutral": 600, "joyful": 200, "calm": 200},
            )
        ],
    )
    assert MoodConcentrationRule()(obs) == []


def test_fleet_unreachable_fires_critical():
    obs = Observation(
        ts=0,
        shards=[ShardHealthz(shard=1, reachable=False, error="connection refused")],
    )
    proposals = FleetUnreachableRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].severity == "critical"
    assert proposals[0].suggested_action.kind == "issue-only"
    assert "human" in proposals[0].pr_agent_hint.reviewers
    assert "on-call" in proposals[0].pr_agent_hint.reviewers


# ── Queue sampling ────────────────────────────────────────────────────


def test_sample_queue_reads_ndjson_correctly(tmp_path: Path):
    queue = tmp_path / "shard-0.ndjson"
    lines = [
        json.dumps({"v": 1, "ts": 1, "mood": "joyful", "contentSourceKind": "inbound", "code": "10101500"}),
        json.dumps({"v": 1, "ts": 2, "mood": "joyful", "contentSourceKind": "inbound", "code": "10101501"}),
        json.dumps({"v": 1, "ts": 3, "mood": "calm", "contentSourceKind": "reaction", "code": "10101500"}),
    ]
    queue.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sample = sample_queue(queue)
    assert sample.shard == 0
    assert sample.sample_count == 3
    assert sample.mood_distribution == {"joyful": 2, "calm": 1}
    assert sample.content_source_distribution == {"inbound": 2, "reaction": 1}
    assert sample.unique_codes == 2
    assert sample.earliest_ts == 1
    assert sample.latest_ts == 3


def test_sample_queue_missing_file():
    sample = sample_queue("/nonexistent/shard-0.ndjson")
    assert sample.sample_count == 0
    assert sample.mood_distribution == {}


def test_sample_queue_tail_lines(tmp_path: Path):
    queue = tmp_path / "shard-0.ndjson"
    lines = [
        json.dumps({"v": 1, "ts": i, "mood": "joyful", "code": str(i)}) for i in range(500)
    ]
    queue.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sample = sample_queue(queue, tail_lines=100)
    assert sample.sample_count <= 100  # may be slightly less due to tail window
    assert sample.sample_count > 0


# ── Proposal NDJSON schema ────────────────────────────────────────────


def test_proposal_serialization_matches_schema():
    proposal = KaizenProposal(
        rule_id="x",
        category="performance",
        severity="warn",
        actor_scope="shard:1",
        summary="s",
        detail="d",
        evidence={"a": 1},
        suggested_action=SuggestedAction(
            kind="config-change",
            description="bump",
            target_files=["a.yaml"],
            patch_hint="X → Y",
            test_plan=["t1", "t2"],
        ),
        pr_agent_hint=PrAgentHint(branch_prefix="kaizen/x-", labels=["kaizen"]),
    )
    payload = proposal.to_ndjson_dict(1000)
    assert payload["v"] == PROPOSAL_SCHEMA_VERSION
    assert payload["kind"] == "kaizen-proposal"
    assert payload["ruleId"] == "x"
    assert payload["suggestedAction"]["kind"] == "config-change"
    assert payload["suggestedAction"]["targetFiles"] == ["a.yaml"]
    assert payload["prAgentHint"]["branchPrefix"] == "kaizen/x-"
    assert payload["createdAt"].endswith("Z")


# ── KaizenObserver end-to-end ─────────────────────────────────────────


def _fake_healthz(shard: int, **overrides) -> dict:
    body = {
        "ok": True,
        "service": "OrganismFleetCell",
        "shard": shard,
        "ownedCount": 4000 + shard * 1000,
        "warmCount": 2000,
        "warmCapacity": 4096,
        "tickCount": 20,
        "lastTickDurationMs": 500.0,
        "totalPosts": 100,
        "totalClassifications": 1000,
        "totalErrors": 0,
        "uptimeS": 600,
    }
    body.update(overrides)
    return body


def test_observer_tick_with_healthy_fleet_emits_no_proposals(tmp_path: Path):
    proposal_path = tmp_path / "observer.ndjson"
    bodies = {
        "http://shard-0:13040": _fake_healthz(0),
        "http://shard-1:13050": _fake_healthz(1),
        "http://shard-2:13060": _fake_healthz(2),
    }

    def http_get(url: str, _timeout: float) -> dict:
        return bodies[url]

    observer = KaizenObserver(
        shard_urls=list(bodies.keys()),
        queue_paths=[],
        proposal_path=proposal_path,
        http_get=http_get,
    )
    # Build up enough history so latency rule has data
    for i in range(30):
        observer.tick(now_ms=1000 + i * 1000)
    assert proposal_path.read_text(encoding="utf-8") == ""


def test_observer_tick_detects_unreachable_shard(tmp_path: Path):
    proposal_path = tmp_path / "observer.ndjson"

    def http_get(url: str, _timeout: float) -> dict:
        raise ConnectionRefusedError(f"connection refused: {url}")

    observer = KaizenObserver(
        shard_urls=["http://down:13040"],
        queue_paths=[],
        proposal_path=proposal_path,
        http_get=http_get,
        dedup_window_s=0,  # disable dedup for the test
    )
    status = observer.tick(now_ms=1000)
    assert status["reachable"] == 0
    assert status["proposalsWritten"] >= 1
    lines = proposal_path.read_text(encoding="utf-8").splitlines()
    assert lines  # at least one proposal
    proposals = [json.loads(line) for line in lines]
    assert any(p["ruleId"] == "fleet-unreachable" for p in proposals)


def test_observer_detects_lru_saturation(tmp_path: Path):
    proposal_path = tmp_path / "observer.ndjson"
    body = _fake_healthz(0, warmCount=4096, warmCapacity=4096, ownedCount=4597)

    def http_get(url: str, _timeout: float) -> dict:
        return body

    observer = KaizenObserver(
        shard_urls=["http://shard-0:13040"],
        queue_paths=[],
        proposal_path=proposal_path,
        http_get=http_get,
        dedup_window_s=0,
    )
    observer.tick(now_ms=1000)
    proposals = [
        json.loads(line) for line in proposal_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(p["ruleId"] == "lru-saturation" for p in proposals)


def test_observer_dedups_same_rule_within_window(tmp_path: Path):
    proposal_path = tmp_path / "observer.ndjson"
    body = _fake_healthz(0, warmCount=4096, warmCapacity=4096, ownedCount=4597)

    def http_get(url: str, _timeout: float) -> dict:
        return body

    observer = KaizenObserver(
        shard_urls=["http://shard-0:13040"],
        queue_paths=[],
        proposal_path=proposal_path,
        http_get=http_get,
        dedup_window_s=7200,
    )
    s1 = observer.tick(now_ms=1000)
    s2 = observer.tick(now_ms=1000 + 60 * 1000)  # 1 min later — same window
    assert s1["proposalsWritten"] >= 1
    assert s2["proposalsWritten"] == 0  # dedup'd


def test_observer_status_dict_shape(tmp_path: Path):
    body = _fake_healthz(0)

    def http_get(url: str, _timeout: float) -> dict:
        return body

    observer = KaizenObserver(
        shard_urls=["http://shard-0:13040"],
        queue_paths=[],
        proposal_path=tmp_path / "obs.ndjson",
        http_get=http_get,
    )
    status = observer.tick(now_ms=1000)
    assert set(status.keys()) >= {
        "tickCount",
        "shardCount",
        "reachable",
        "proposalsRaised",
        "proposalsAfterDedup",
        "proposalsWritten",
    }


def test_observer_actor_did_is_kaizen():
    observer = KaizenObserver(
        shard_urls=[],
        queue_paths=[],
        proposal_path=Path("/tmp/x.ndjson"),
    )
    assert observer.actor_did == "did:web:etzhayyim.com:actor:kaizen-observer"


# ── kaizen_cell_main fire() smoke ─────────────────────────────────────


@pytest.mark.asyncio
async def test_kaizen_fire_returns_status_dict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import kotodama.organism.kaizen_cell_main as km

    monkeypatch.setenv("KAIZEN_PROPOSAL_PATH", str(tmp_path / "obs.ndjson"))
    monkeypatch.setenv("KAIZEN_SHARD_URLS", "http://unreachable:0")
    km._observer = None  # reset module-level singleton
    status = await km.fire()
    assert "tickCount" in status
    assert status["tickCount"] == 1
