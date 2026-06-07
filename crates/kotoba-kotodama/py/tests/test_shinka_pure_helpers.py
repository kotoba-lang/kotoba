"""Tests for pure helper functions in shinka/__init__.py:
_classify_mood, _cadence_flags."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# conftest installs langgraph stub; just import directly
from kotodama.shinka import (  # noqa: E402
    _classify_mood, _cadence_flags, _resolve_cadence,
    _kyumei_gather, _koji_validate, _shinka_analyze, _compose_content, _emit_evolution,
)

_MIN_MS = 60 * 1000  # 1 minute in ms


# ─── _classify_mood ──────────────────────────────────────────────────────────

def test_classify_mood_stressed_dominates() -> None:
    axes = {"stress": 70, "joy": 80, "calm": 80}
    assert _classify_mood(axes) == "stressed"


def test_classify_mood_joyful() -> None:
    axes = {"joy": 60, "stress": 0}
    assert _classify_mood(axes) == "joyful"


def test_classify_mood_calm() -> None:
    axes = {"calm": 60, "joy": 0, "stress": 0}
    assert _classify_mood(axes) == "calm"


def test_classify_mood_grateful() -> None:
    axes = {"gratitude": 60, "calm": 0, "joy": 0, "stress": 0}
    assert _classify_mood(axes) == "grateful"


def test_classify_mood_focused() -> None:
    axes = {"focus": 60, "gratitude": 0, "calm": 0, "joy": 0, "stress": 0}
    assert _classify_mood(axes) == "focused"


def test_classify_mood_neutral_when_all_low() -> None:
    axes = {"joy": 0, "calm": 0, "stress": 0, "gratitude": 0, "focus": 0}
    assert _classify_mood(axes) == "neutral"


def test_classify_mood_neutral_empty_axes() -> None:
    assert _classify_mood({}) == "neutral"


def test_classify_mood_stress_threshold_exact() -> None:
    # 70 triggers stressed; 69 does not
    assert _classify_mood({"stress": 70}) == "stressed"
    assert _classify_mood({"stress": 69}) != "stressed"


def test_classify_mood_returns_literal_string() -> None:
    result = _classify_mood({"joy": 70})
    assert isinstance(result, str)
    assert result in ("joyful", "calm", "stressed", "grateful", "focused", "neutral")


# ─── _cadence_flags ──────────────────────────────────────────────────────────

def test_cadence_flags_returns_dict() -> None:
    flags = _cadence_flags("neutral", 0)
    assert isinstance(flags, dict)


def test_cadence_flags_all_keys_present() -> None:
    flags = _cadence_flags("neutral", 0)
    assert "should_post" in flags
    assert "should_engage" in flags
    assert "should_drill" in flags
    assert "should_validate" in flags
    assert "should_analyze" in flags


def test_cadence_flags_stressed_no_post_or_engage() -> None:
    flags = _cadence_flags("stressed", 0)
    assert flags["should_post"] is False
    assert flags["should_engage"] is False


def test_cadence_flags_stressed_drill_after_30_min() -> None:
    flags_before = _cadence_flags("stressed", 29 * _MIN_MS)
    flags_after = _cadence_flags("stressed", 31 * _MIN_MS)
    assert flags_before["should_drill"] is False
    assert flags_after["should_drill"] is True


def test_cadence_flags_joyful_post_after_30_min() -> None:
    flags_before = _cadence_flags("joyful", 29 * _MIN_MS)
    flags_after = _cadence_flags("joyful", 31 * _MIN_MS)
    assert flags_before["should_post"] is False
    assert flags_after["should_post"] is True


def test_cadence_flags_joyful_no_drill() -> None:
    flags = _cadence_flags("joyful", 999 * _MIN_MS)
    assert flags["should_drill"] is False


def test_cadence_flags_calm_post_after_120_min() -> None:
    flags_before = _cadence_flags("calm", 119 * _MIN_MS)
    flags_after = _cadence_flags("calm", 121 * _MIN_MS)
    assert flags_before["should_post"] is False
    assert flags_after["should_post"] is True


def test_cadence_flags_focused_no_engage() -> None:
    flags = _cadence_flags("focused", 999 * _MIN_MS)
    assert flags["should_engage"] is False


def test_cadence_flags_focused_post_after_180_min() -> None:
    flags_before = _cadence_flags("focused", 179 * _MIN_MS)
    flags_after = _cadence_flags("focused", 181 * _MIN_MS)
    assert flags_before["should_post"] is False
    assert flags_after["should_post"] is True


def test_cadence_flags_grateful_engage_after_10_min() -> None:
    flags_before = _cadence_flags("grateful", 9 * _MIN_MS)
    flags_after = _cadence_flags("grateful", 11 * _MIN_MS)
    assert flags_before["should_engage"] is False
    assert flags_after["should_engage"] is True


def test_cadence_flags_neutral_elapsed_zero_all_false() -> None:
    flags = _cadence_flags("neutral", 0)
    assert all(v is False for v in flags.values())


def test_cadence_flags_values_are_bool() -> None:
    flags = _cadence_flags("neutral", 999 * _MIN_MS)
    assert all(isinstance(v, bool) for v in flags.values())


# ─── _resolve_cadence ────────────────────────────────────────────────────────

def test_resolve_cadence_returns_state_with_flags() -> None:
    state = {"now_ms": 10_000_000, "last_heartbeat_ms": 0, "mood": "neutral", "actor_did": "did:web:test"}
    result = _resolve_cadence(state)
    assert "should_post" in result
    assert "should_engage" in result
    assert "should_drill" in result
    assert "should_validate" in result
    assert "should_analyze" in result


def test_resolve_cadence_actions_reset_to_empty() -> None:
    state = {"now_ms": 10_000_000, "last_heartbeat_ms": 0, "mood": "neutral",
             "actor_did": "did:web:test", "actions": ["old-action"]}
    result = _resolve_cadence(state)
    assert result["actions"] == []


def test_resolve_cadence_preserves_actor_did() -> None:
    state = {"now_ms": 1_000_000, "last_heartbeat_ms": 0, "mood": "joyful",
             "actor_did": "did:web:actor.etzhayyim.com"}
    result = _resolve_cadence(state)
    assert result["actor_did"] == "did:web:actor.etzhayyim.com"


def test_resolve_cadence_stressed_disables_post() -> None:
    # stressed mood disables should_post regardless of elapsed
    state = {"now_ms": 999_000_000, "last_heartbeat_ms": 0, "mood": "stressed",
             "actor_did": "did:web:test"}
    result = _resolve_cadence(state)
    assert result["should_post"] is False


def test_resolve_cadence_no_last_heartbeat_uses_zero() -> None:
    # no last_heartbeat_ms → elapsed = now_ms
    state = {"now_ms": 5_000_000, "mood": "joyful", "actor_did": "did:web:test"}
    result = _resolve_cadence(state)
    assert isinstance(result["should_post"], bool)


def test_resolve_cadence_flags_are_bools() -> None:
    state = {"now_ms": 10_000_000, "last_heartbeat_ms": 5_000_000, "mood": "calm",
             "actor_did": "did:web:test"}
    result = _resolve_cadence(state)
    for key in ("should_post", "should_engage", "should_drill", "should_validate", "should_analyze"):
        assert isinstance(result[key], bool)


# ─── _kyumei_gather early-return ─────────────────────────────────────────────

def test_kyumei_gather_no_drill_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "mood": "calm",
             "should_drill": False, "actions": []}
    result = _kyumei_gather(state)
    assert result is state


def test_kyumei_gather_no_drill_key_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "mood": "calm", "actions": []}
    result = _kyumei_gather(state)
    assert result is state


# ─── _koji_validate early-return ─────────────────────────────────────────────

def test_koji_validate_no_validate_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "mood": "calm",
             "should_validate": False, "actions": []}
    result = _koji_validate(state)
    assert result is state


def test_koji_validate_no_validate_key_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "actions": []}
    result = _koji_validate(state)
    assert result is state


# ─── _shinka_analyze early-return ────────────────────────────────────────────

def test_shinka_analyze_no_analyze_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "mood": "calm",
             "should_analyze": False, "actions": []}
    result = _shinka_analyze(state)
    assert result is state


def test_shinka_analyze_no_analyze_key_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "actions": []}
    result = _shinka_analyze(state)
    assert result is state


# ─── _compose_content early-return ───────────────────────────────────────────

def test_compose_content_no_post_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "mood": "calm",
             "should_post": False, "actions": []}
    result = _compose_content(state)
    assert result is state


def test_compose_content_no_post_key_returns_state_unchanged() -> None:
    state = {"actor_did": "did:web:test", "now_ms": 1_000_000, "mood": "calm", "actions": []}
    result = _compose_content(state)
    assert result is state


# ─── _emit_evolution early-return ────────────────────────────────────────────
# _emit_evolution always runs (no early-return guard) — skip; tested via integration only.
