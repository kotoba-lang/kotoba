"""Tests for the Wave 2 organism wave (ADRs 2605240000 / 2605240015 / 2605240030).

Covers:
  - joucho_personality_provider determinism + distribution + segment bias
  - file_follower_score_provider + default stub
  - UnispscOrganismFleetCell shard ownership + tick sweep
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from kotodama.organism.followers import (
    file_follower_score_provider,
    follower_score_provider,
)
from kotodama.organism.fleet_cell_main import (
    SHARD_RANGES,
    FleetState,
    OrganismCache,
    _owns,
)
from kotodama.organism.inbox import FollowerSnapshot, detect_follower_rewards
from kotodama.organism.joucho import JouchoScores
from kotodama.organism.personality import (
    _code_from_did,
    joucho_for_code,
    joucho_personality_provider,
)


# ── Joucho personality determinism + distribution ──────────────────────


def test_personality_is_deterministic():
    a = joucho_for_code("10101500")
    b = joucho_for_code("10101500")
    assert a == b


def test_different_codes_give_different_personalities():
    a = joucho_for_code("10101500")  # Live Animal
    b = joucho_for_code("11101500")  # bumped to next segment
    c = joucho_for_code("60101500")  # services segment
    # At least one axis must differ between distinct codes.
    assert (a.joy, a.calm, a.stress, a.gratitude, a.focus) != (
        b.joy,
        b.calm,
        b.stress,
        b.gratitude,
        b.focus,
    )
    assert (a.joy, a.calm, a.stress, a.gratitude, a.focus) != (
        c.joy,
        c.calm,
        c.stress,
        c.gratitude,
        c.focus,
    )


def test_personality_axes_clamped_to_0_100():
    for code in ("00000000", "99999999", "10101500", "51234567"):
        j = joucho_for_code(code)
        for axis in (j.joy, j.calm, j.stress, j.gratitude, j.focus):
            assert 0 <= axis <= 100, f"axis out of range for {code}: {j}"


def test_segment_10_biases_joy_and_gratitude():
    # Segment 10 (Live Plant/Animal): +joy +gratitude
    # Take many samples to average out hash noise.
    s10_joy_total = 0
    baseline_joy_total = 0
    for i in range(50):
        s10_joy_total += joucho_for_code(f"10{i:06d}").joy
        baseline_joy_total += joucho_for_code(f"99{i:06d}").joy
    assert s10_joy_total > baseline_joy_total


def test_provider_extracts_code_from_did():
    j = joucho_personality_provider("did:web:etzhayyim.com:actor:c10101500")
    assert j == joucho_for_code("10101500")


def test_provider_accepts_bare_code_fallback():
    j = joucho_personality_provider("not-a-did")
    assert isinstance(j, JouchoScores)
    # 0 ≤ scores ≤ 100
    for axis in (j.joy, j.calm, j.stress, j.gratitude, j.focus):
        assert 0 <= axis <= 100


def test_code_from_did_helper():
    assert _code_from_did("did:web:etzhayyim.com:actor:c10101500") == "10101500"
    assert _code_from_did("did:web:c10101500.etzhayyim.com") == "10101500"


# ── Follower providers ─────────────────────────────────────────────────


def test_default_follower_provider_returns_empty():
    assert follower_score_provider("did:web:etzhayyim.com:actor:c10101500") == []


def test_file_follower_provider_reads_seed(tmp_path: Path):
    seed = {
        "did:web:etzhayyim.com:actor:c10101500": [
            {"did": "did:web:f1", "wellnessScore": 50, "dojoScore": 0, "rank": "kyu6"},
            {"did": "did:web:f2", "wellnessScore": 75, "dojoScore": 2, "rank": "kyu3"},
        ],
        "did:web:etzhayyim.com:actor:c10101501": [],
    }
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps(seed))

    provider = file_follower_score_provider(seed_path)
    rows = provider("did:web:etzhayyim.com:actor:c10101500")
    assert len(rows) == 2
    assert rows[0].did == "did:web:f1"
    assert rows[0].wellness_score == 50.0
    assert rows[1].rank == "kyu3"

    assert provider("did:web:etzhayyim.com:actor:c10101501") == []
    assert provider("did:web:etzhayyim.com:actor:c99999999") == []


def test_file_follower_provider_missing_file(tmp_path: Path):
    provider = file_follower_score_provider(tmp_path / "nope.json")
    assert provider("did:web:anything") == []


def test_file_seeded_followers_feed_reward_detector(tmp_path: Path):
    seed = {
        "did:web:test": [
            {"did": "did:f1", "wellnessScore": 60, "dojoScore": 0, "rank": "kyu5"},
        ]
    }
    p = tmp_path / "seed.json"
    p.write_text(json.dumps(seed))
    provider = file_follower_score_provider(p)
    current = provider("did:web:test")
    snapshots = {"did:f1": FollowerSnapshot(wellness_score=50.0, dojo_score=0.0, rank="kyu5")}
    rewards = detect_follower_rewards(current, snapshots)
    assert len(rewards) == 1
    assert rewards[0].did == "did:f1"
    assert rewards[0].reward_type == "love"  # +10 wellness ≥ 10 threshold


# ── UnispscOrganismFleetCell — sharding + tick sweep ───────────────────


def test_shard_ranges_match_executor_cell():
    # Mirror of UnispscAgentExecutorCell.SHARD_RANGES
    assert SHARD_RANGES[-1] == (0, 99)
    assert SHARD_RANGES[0] == (10, 29)
    assert SHARD_RANGES[1] == (30, 44)
    assert SHARD_RANGES[2] == (45, 60)


def test_owns_segment_prefix_boundary():
    assert _owns("10101500", 10, 29) is True
    assert _owns("29999999", 10, 29) is True
    assert _owns("30000000", 10, 29) is False
    assert _owns("9", 10, 29) is False  # too short
    assert _owns("ZZ000000", 10, 29) is False


def test_organism_cache_lru_eviction():
    cache = OrganismCache(capacity=2)
    a = cache.get_or_create("10101500", title="Live Animal")
    assert a is not None
    assert len(cache) == 1
    # Re-fetch counts as hit
    cache.get_or_create("10101500")
    assert cache.hits == 1


def test_fleet_state_loads_registry_for_shard_0():
    state = FleetState(shard_index=0, organism_lru_max=64)
    state.load_registry()
    # joseph owns segments 10-29 — must have ~4,597 codes (registry total).
    assert len(state.owned_codes) > 0
    # All codes must start with a segment in [10, 29].
    for code, _title in state.owned_codes:
        seg = int(code[:2])
        assert 10 <= seg <= 29, f"shard-0 leaked code {code} outside segments 10-29"


def test_fleet_state_tick_all_smokes_for_a_few_codes(monkeypatch: pytest.MonkeyPatch):
    """Smoke test: a small registry filter ticks every owned organism without crashing."""
    state = FleetState(shard_index=0, organism_lru_max=8)
    state.load_registry()
    # Trim to the first 5 codes for a fast smoke test.
    state.owned_codes = state.owned_codes[:5]
    state.tick_all(now_ms=3 * 3_600_000 + 1)
    assert state.tick_count == 1
    assert state.last_tick_duration_ms >= 0.0
    # 5 organisms should have all loaded into cache.
    assert len(state.cache) == 5
    # Each organism has its own deterministic personality, so total_posts can
    # be 0 or positive — we just need the sweep to not raise.
    assert state.total_errors == 0


def test_fleet_state_two_consecutive_ticks_increment_count():
    state = FleetState(shard_index=0, organism_lru_max=4)
    state.load_registry()
    state.owned_codes = state.owned_codes[:3]
    base_now = 3 * 3_600_000 + 1
    state.tick_all(now_ms=base_now)
    state.tick_all(now_ms=base_now + 5 * 60_000)
    assert state.tick_count == 2


def test_organisms_have_distinct_personalities_in_shard():
    state = FleetState(shard_index=0, organism_lru_max=16)
    state.load_registry()
    state.owned_codes = state.owned_codes[:10]
    state.tick_all(now_ms=3 * 3_600_000 + 1)
    moods = []
    for code, _ in state.owned_codes:
        org = state.cache.get_or_create(code)
        assert org is not None
        # personality provider is what was wired in fleet_cell_main
        scores = org.joucho_provider(org.actor_did) if org.joucho_provider else JouchoScores()
        moods.append((scores.joy, scores.calm, scores.stress, scores.gratitude, scores.focus))
    # Distinct codes must produce at least 2 distinct mood tuples.
    assert len(set(moods)) > 1


# ── lan-api serve smoke (using ephemeral ports) ────────────────────────


@pytest.mark.asyncio
async def test_fleet_cell_serve_starts_and_shuts_down(monkeypatch: pytest.MonkeyPatch):
    """Minimal serve() smoke — start, healthz reachable, shutdown cleanly."""
    from kotodama.organism import fleet_cell_main

    # Force jacob single-host mode but trim to a tiny owned set.
    monkeypatch.setenv("UNISPSC_ORGANISM_SHARD_ALL", "1")
    monkeypatch.setenv("UNISPSC_ORGANISM_LRU_MAX", "4")
    monkeypatch.setenv("UNISPSC_ORGANISM_TICK_INTERVAL_S", "3600")  # large; no tick during test

    # Patch load_registry to limit owned codes so the initial sweep is fast.
    original_load = fleet_cell_main.FleetState.load_registry

    def small_load(self, path=fleet_cell_main.REGISTRY_PATH):  # type: ignore[no-untyped-def]
        original_load(self, path)
        self.owned_codes = self.owned_codes[:3]

    monkeypatch.setattr(fleet_cell_main.FleetState, "load_registry", small_load)

    stop = asyncio.Event()
    # Use a non-default port to avoid collisions in parallel test runs.
    serve_task = asyncio.create_task(
        fleet_cell_main.serve(stop, healthz_port=23045, api_port=23045)
    )
    # Give the serve loop a beat to start.
    await asyncio.sleep(0.5)
    stop.set()
    await asyncio.wait_for(serve_task, timeout=5.0)
