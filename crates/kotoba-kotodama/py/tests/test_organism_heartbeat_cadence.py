"""Tests for kotodama.organism heartbeat-cadence (ADR-2605232345)."""

from __future__ import annotations

import pytest

from kotodama.organism import (
    CadenceState,
    InboxBuffer,
    JouchoScores,
    UnispscOrganism,
    determine_mood,
    resolve_heartbeat_cadence,
)
from kotodama.organism.inbox import (
    FollowerCurrentScore,
    FollowerSnapshot,
    InboundCommit,
    InboundReaction,
    detect_follower_rewards,
)
from kotodama.organism.joucho import apply_stress_scaling, mood_to_cadence


# ── Mood determination — match TS thresholds ───────────────────────────


def test_stress_at_70_trumps_other_axes():
    j = JouchoScores(joy=95, calm=95, stress=70, gratitude=95, focus=95)
    assert determine_mood(j) == "stressed"


def test_stress_at_69_does_not_trump():
    j = JouchoScores(joy=80, calm=20, stress=69, gratitude=20, focus=20)
    assert determine_mood(j) == "joyful"


def test_dominant_axis_at_60_wins():
    j = JouchoScores(joy=10, calm=60, stress=10, gratitude=10, focus=10)
    assert determine_mood(j) == "calm"


def test_all_axes_below_60_returns_neutral():
    j = JouchoScores(joy=59, calm=59, stress=10, gratitude=59, focus=59)
    assert determine_mood(j) == "neutral"


def test_focus_dominant():
    j = JouchoScores(joy=40, calm=40, stress=10, gratitude=40, focus=85)
    assert determine_mood(j) == "focused"


# ── Cooldown table — spot-check known TS values ────────────────────────


def test_joyful_post_cooldown_30min():
    assert mood_to_cadence("joyful").post_cooldown_ms == 30 * 60_000


def test_stressed_post_disabled():
    assert mood_to_cadence("stressed").post_enabled is False


def test_stress_scaling_increases_post_cooldown():
    base = mood_to_cadence("calm")
    scaled = apply_stress_scaling(base, stress=75)
    assert scaled.post_cooldown_ms > base.post_cooldown_ms
    # 75 stress → scale = 1.5
    assert scaled.post_cooldown_ms == round(base.post_cooldown_ms * 1.5)


def test_stress_scaling_below_threshold_is_noop():
    base = mood_to_cadence("calm")
    scaled = apply_stress_scaling(base, stress=49)
    assert scaled.post_cooldown_ms == base.post_cooldown_ms


# ── Cooldown gates ─────────────────────────────────────────────────────


def test_first_tick_should_not_post_when_cooldown_not_elapsed():
    state = CadenceState(last_post_at=1000)
    inbox = InboxBuffer()
    # 1 second after last post — well under any cooldown
    result = resolve_heartbeat_cadence("did:test", state, inbox, now_ms=2000)
    assert result.should_post is False


def test_after_cooldown_should_post():
    state = CadenceState()  # all zeros = last post at epoch
    inbox = InboxBuffer()
    # 3 hours in — past any neutral cooldown
    result = resolve_heartbeat_cadence("did:test", state, inbox, now_ms=3 * 3_600_000 + 1)
    assert result.should_post is True


# ── ContentSource resolution ───────────────────────────────────────────


def test_inbound_commit_drives_inbound_content_source():
    state = CadenceState()
    inbox = InboxBuffer()
    inbox.add_commit(
        InboundCommit(collection="x", repo="did:other", rkey="rk1", time="t")
    )
    result = resolve_heartbeat_cadence(
        "did:test", state, inbox, now_ms=3 * 3_600_000 + 1
    )
    assert result.content_source.kind == "inbound"


def test_reaction_drives_reaction_in_calm_mood():
    state = CadenceState()
    inbox = InboxBuffer()
    inbox.add_reaction(InboundReaction(type="like", uri="at://x", from_="did:f", time="t"))

    def jp(_did: str) -> JouchoScores:
        return JouchoScores(joy=20, calm=80, stress=10, gratitude=20, focus=20)

    result = resolve_heartbeat_cadence(
        "did:test", state, inbox, now_ms=3 * 3_600_000 + 1, joucho_provider=jp
    )
    assert result.mood == "calm"
    assert result.content_source.kind == "reaction"


def test_empty_inbox_falls_back_to_record_analysis():
    state = CadenceState()
    inbox = InboxBuffer()
    result = resolve_heartbeat_cadence("did:test", state, inbox, now_ms=3 * 3_600_000 + 1)
    assert result.content_source.kind in ("recordAnalysis", "none")


def test_stressed_mood_yields_none_content_source():
    state = CadenceState()
    inbox = InboxBuffer()
    inbox.add_commit(InboundCommit(collection="x", repo="r", rkey="rk", time="t"))

    def jp(_did: str) -> JouchoScores:
        return JouchoScores(joy=10, calm=10, stress=80, gratitude=10, focus=10)

    result = resolve_heartbeat_cadence(
        "did:test", state, inbox, now_ms=3 * 3_600_000 + 1, joucho_provider=jp
    )
    assert result.mood == "stressed"
    assert result.should_post is False
    assert result.content_source.kind == "none"


# ── FollowerReward delta detection ─────────────────────────────────────


def test_follower_wellness_improvement_emits_like():
    snapshots = {"did:f": FollowerSnapshot(wellness_score=50, dojo_score=0, rank="kyu6")}
    current = [
        FollowerCurrentScore(
            did="did:f",
            wellness_score=55,  # +5 → like
            dojo_score=0,
            rank="kyu6",
        )
    ]
    rewards = detect_follower_rewards(current, snapshots)
    assert len(rewards) == 1
    assert rewards[0].reward_type == "like"
    assert rewards[0].metric == "wellness"


def test_follower_large_wellness_jump_emits_love():
    snapshots = {"did:f": FollowerSnapshot(wellness_score=50, dojo_score=0, rank="kyu6")}
    current = [
        FollowerCurrentScore(did="did:f", wellness_score=65, dojo_score=0, rank="kyu6"),  # +15 → love
    ]
    rewards = detect_follower_rewards(current, snapshots)
    assert rewards[0].reward_type == "love"


def test_follower_no_snapshot_no_reward():
    rewards = detect_follower_rewards(
        [FollowerCurrentScore(did="did:f", wellness_score=99, dojo_score=99, rank="kyu1")],
        snapshots={},
    )
    assert rewards == []


def test_follower_negative_delta_no_reward():
    snapshots = {"did:f": FollowerSnapshot(wellness_score=80, dojo_score=5, rank="kyu5")}
    current = [
        FollowerCurrentScore(did="did:f", wellness_score=70, dojo_score=5, rank="kyu5"),  # -10
    ]
    assert detect_follower_rewards(current, snapshots) == []


# ── InboxBuffer bounds ─────────────────────────────────────────────────


def test_inbox_caps_commits_at_100():
    inbox = InboxBuffer()
    for i in range(150):
        inbox.add_commit(InboundCommit(collection="x", repo="r", rkey=str(i), time="t"))
    assert len(inbox.inbound_commits) == 100
    # Oldest dropped first
    assert inbox.inbound_commits[0].rkey == "50"


def test_inbox_caps_reactions_at_50():
    inbox = InboxBuffer()
    for i in range(80):
        inbox.add_reaction(InboundReaction(type="like", uri=str(i), from_="did:f", time="t"))
    assert len(inbox.reactions) == 50


# ── Shannon content diversity ──────────────────────────────────────────


def test_three_consecutive_record_analysis_posts_get_suppressed():
    state = CadenceState()
    inbox = InboxBuffer()

    # Three ticks past the cooldown with no inbox → recordAnalysis each time
    base_now = 3 * 3_600_000 + 1
    r1 = resolve_heartbeat_cadence("did:test", state, inbox, now_ms=base_now)
    assert r1.content_source.kind == "recordAnalysis"

    # Reset post cooldown so a second post is allowed by mood gate
    state.last_post_at = 0
    r2 = resolve_heartbeat_cadence("did:test", state, inbox, now_ms=base_now + 1)
    assert r2.content_source.kind == "recordAnalysis"

    state.last_post_at = 0
    r3 = resolve_heartbeat_cadence("did:test", state, inbox, now_ms=base_now + 2)
    # Saturation gate kicks in — must fall back to something else (or none)
    assert r3.content_source.kind != "recordAnalysis"


# ── UnispscOrganism end-to-end ─────────────────────────────────────────


def test_organism_wraps_c10101500_without_modifying_graph():
    organism = UnispscOrganism.for_code("10101500")
    assert organism.code == "10101500"
    assert organism.title == "Live Animal"
    assert organism.actor_did == "did:web:etzhayyim.com:actor:c10101500"

    # Graph remains the original — invoke still works directly.
    terminal = organism.graph.invoke({"input": {"species": "ovis aries", "health_data": {"certified": True}}})
    assert terminal["health_certified"] is True
    assert terminal["quarantine_status"] == "cleared"
    assert terminal["result"]["status"] == "authorized"


def test_organism_tick_with_empty_inbox_produces_cadence():
    organism = UnispscOrganism.for_code("10101500")
    # First tick: cooldowns all zero, so neutral mood will permit some action.
    result = organism.tick(now_ms=3 * 3_600_000 + 1)
    assert result.cadence.mood in ("neutral", "calm", "joyful", "grateful", "focused", "stressed")
    assert isinstance(result.classifications, list)
    assert isinstance(result.posts, list)


def test_organism_tick_with_inbound_commit_runs_classify():
    captured: list[str] = []
    organism = UnispscOrganism.for_code(
        "10101500",
        classify_input_factory=lambda _c: {
            "input": {"species": "ovis aries", "health_data": {"certified": True}},
        },
        post_sink=lambda text: captured.append(text),
    )
    organism.lifecycle.handle_birth(organism.actor_did)
    organism.inbox.add_commit(
        InboundCommit(collection="x", repo="did:other", rkey="r1", time="t")
    )
    result = organism.tick(now_ms=3 * 3_600_000 + 1)
    # Inbound source should drive classify + post.
    assert result.cadence.should_post is True
    assert result.cadence.content_source.kind == "inbound"
    assert len(result.classifications) == 1
    assert result.classifications[0]["result"]["status"] == "authorized"
    assert any("[10101500/Live Animal]" in p for p in result.posts)
    assert captured  # post_sink was invoked


def test_organism_classify_failure_does_not_crash_tick():
    organism = UnispscOrganism.for_code(
        "10101500",
        classify_input_factory=lambda _c: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    organism.inbox.add_commit(
        InboundCommit(collection="x", repo="did:other", rkey="r1", time="t")
    )
    result = organism.tick(now_ms=3 * 3_600_000 + 1)
    # Classify raised, but tick survived.
    assert result.classifications == []


# ── cell_main entry point ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cell_main_fire_returns_status():
    # Reset module-level organism between tests so env override is honored.
    import kotodama.organism.cell_main as cell_main

    cell_main._organism = None
    status = await cell_main.fire()
    assert status["code"] == "10101500"
    assert status["tickCount"] == 1
    assert "mood" in status
    assert "posts" in status
