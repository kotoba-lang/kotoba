"""Tests for pure helpers in agents/gameka_studio.py:
_slugify, _safe_float, _safe_int, _should_loop."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_agent_gameka_studio"
if _MOD_NAME in sys.modules:
    GS = sys.modules[_MOD_NAME]
else:
    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    GS = _load_mod(_MOD_NAME, "kotodama/agents/gameka_studio.py")


# ─── _slugify ────────────────────────────────────────────────────────────────

def test_slugify_plain_string() -> None:
    assert GS._slugify("my game") == "my-game"


def test_slugify_lowercases() -> None:
    result = GS._slugify("My Game")
    assert result == result.lower()


def test_slugify_strips_special_chars() -> None:
    result = GS._slugify("Game: #1!")
    assert "#" not in result
    assert "!" not in result
    assert ":" not in result


def test_slugify_none_returns_game() -> None:
    assert GS._slugify(None) == "game"


def test_slugify_empty_returns_game() -> None:
    assert GS._slugify("") == "game"


def test_slugify_truncates_at_24() -> None:
    result = GS._slugify("a" * 50)
    assert len(result) <= 24


def test_slugify_no_leading_hyphen() -> None:
    result = GS._slugify("  game  ")
    assert not result.startswith("-")


def test_slugify_no_trailing_hyphen() -> None:
    result = GS._slugify("game  ")
    assert not result.endswith("-")


def test_slugify_multiple_spaces_to_single_hyphen() -> None:
    result = GS._slugify("a  b")
    assert result == "a-b"


def test_slugify_digits_preserved() -> None:
    result = GS._slugify("game2025")
    assert "2025" in result


# ─── _safe_float ─────────────────────────────────────────────────────────────

def test_safe_float_in_range() -> None:
    assert GS._safe_float(0.5, 0.0, 0.0, 1.0) == 0.5


def test_safe_float_below_lo_clamped() -> None:
    assert GS._safe_float(-1.0, 0.5, 0.0, 1.0) == 0.0


def test_safe_float_above_hi_clamped() -> None:
    assert GS._safe_float(2.0, 0.5, 0.0, 1.0) == 1.0


def test_safe_float_none_returns_default() -> None:
    assert GS._safe_float(None, 0.5, 0.0, 1.0) == 0.5


def test_safe_float_nan_returns_default() -> None:
    import math
    result = GS._safe_float(float("nan"), 0.5, 0.0, 1.0)
    assert result == 0.5


def test_safe_float_string_numeric() -> None:
    assert GS._safe_float("0.8", 0.0, 0.0, 1.0) == 0.8


def test_safe_float_string_non_numeric_returns_default() -> None:
    assert GS._safe_float("abc", 0.5, 0.0, 1.0) == 0.5


def test_safe_float_at_boundaries() -> None:
    assert GS._safe_float(0.0, 0.5, 0.0, 1.0) == 0.0
    assert GS._safe_float(1.0, 0.5, 0.0, 1.0) == 1.0


# ─── _safe_int ───────────────────────────────────────────────────────────────

def test_safe_int_in_range() -> None:
    assert GS._safe_int(5, 3, 1, 10) == 5


def test_safe_int_below_lo_clamped() -> None:
    assert GS._safe_int(0, 3, 1, 10) == 1


def test_safe_int_above_hi_clamped() -> None:
    assert GS._safe_int(20, 3, 1, 10) == 10


def test_safe_int_none_returns_default() -> None:
    assert GS._safe_int(None, 3, 1, 10) == 3


def test_safe_int_string_numeric() -> None:
    assert GS._safe_int("7", 3, 1, 10) == 7


def test_safe_int_float_truncated() -> None:
    assert GS._safe_int(4.9, 3, 1, 10) == 4


def test_safe_int_non_numeric_returns_default() -> None:
    assert GS._safe_int("x", 3, 1, 10) == 3


# ─── _should_loop ────────────────────────────────────────────────────────────

def test_should_loop_low_score_continues() -> None:
    state = {"iteration": 0, "maxIterations": 3, "scoreThreshold": 0.8, "score": 0.4, "candidates": [{}]}
    assert GS._should_loop(state) == "planner"


def test_should_loop_high_score_finalizes() -> None:
    state = {"iteration": 0, "maxIterations": 3, "scoreThreshold": 0.8, "score": 0.9, "candidates": [{}]}
    assert GS._should_loop(state) == "finalizer"


def test_should_loop_max_iterations_reached_finalizes() -> None:
    state = {"iteration": 2, "maxIterations": 3, "scoreThreshold": 0.8, "score": 0.4, "candidates": [{}]}
    assert GS._should_loop(state) == "finalizer"


def test_should_loop_no_candidates_finalizes() -> None:
    state = {"iteration": 0, "maxIterations": 3, "scoreThreshold": 0.8, "score": 0.4, "candidates": []}
    assert GS._should_loop(state) == "finalizer"


def test_should_loop_empty_state_finalizes() -> None:
    # defaults: iteration=0, maxIter=3, threshold=0.8, score=0.0, candidates=[]
    result = GS._should_loop({})
    assert result == "finalizer"


def test_should_loop_returns_string() -> None:
    state = {"iteration": 0, "maxIterations": 3, "scoreThreshold": 0.8, "score": 0.5, "candidates": [{}]}
    assert isinstance(GS._should_loop(state), str)


# ─── _ulid_like ──────────────────────────────────────────────────────────────

def test_ulid_like_contains_prefix() -> None:
    result = GS._ulid_like("game")
    assert result.startswith("game")


def test_ulid_like_returns_string() -> None:
    assert isinstance(GS._ulid_like("pfx"), str)


def test_ulid_like_empty_prefix() -> None:
    result = GS._ulid_like("")
    assert isinstance(result, str)
    assert len(result) > 0


def test_ulid_like_no_hyphens_in_suffix() -> None:
    result = GS._ulid_like("pfx")
    suffix = result[len("pfx"):]
    assert "-" not in suffix


def test_ulid_like_length_is_reasonable() -> None:
    result = GS._ulid_like("pre")
    # prefix(3) + ms_digits(13) + hex_suffix(6) = ~22
    assert len(result) >= 20


def test_ulid_like_hex_suffix_is_lowercase_hex() -> None:
    result = GS._ulid_like("abc")
    suffix = result[-6:]
    assert all(c in "0123456789abcdef" for c in suffix)


# ─── _researcher ─────────────────────────────────────────────────────────────

def test_researcher_dedupes_by_slug() -> None:
    state = {
        "priorSpecs": [{"slug": "my-game", "title": "My Game"}],
        "candidates": [
            {"slug": "my-game", "title": "My Game"},
            {"slug": "new-game", "title": "New Game"},
        ],
    }
    result = GS._researcher(state)
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["slug"] == "new-game"


def test_researcher_dedupes_by_title() -> None:
    state = {
        "priorSpecs": [{"slug": "other", "title": "My Game"}],
        "candidates": [
            {"slug": "different-slug", "title": "My Game"},
            {"slug": "fresh-game", "title": "Fresh Game"},
        ],
    }
    result = GS._researcher(state)
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["slug"] == "fresh-game"


def test_researcher_empty_candidates_returns_empty() -> None:
    state = {"priorSpecs": [], "candidates": []}
    result = GS._researcher(state)
    assert result["candidates"] == []


def test_researcher_no_prior_specs_keeps_all() -> None:
    state = {
        "priorSpecs": [],
        "candidates": [
            {"slug": "game-a", "title": "Game A"},
            {"slug": "game-b", "title": "Game B"},
        ],
    }
    result = GS._researcher(state)
    assert len(result["candidates"]) == 2


def test_researcher_case_insensitive_slug_dedup() -> None:
    state = {
        "priorSpecs": [{"slug": "MY-GAME", "title": "Something"}],
        "candidates": [{"slug": "my-game", "title": "Other Title"}],
    }
    result = GS._researcher(state)
    assert result["candidates"] == []


def test_researcher_preserves_other_state_keys() -> None:
    state = {"priorSpecs": [], "candidates": [], "brief": "Test brief"}
    result = GS._researcher(state)
    assert result["brief"] == "Test brief"


# ─── _finalizer ──────────────────────────────────────────────────────────────

def test_finalizer_returns_spec_id() -> None:
    state = {"candidates": [{"title": "Cool Game", "slug": "cool-game"}]}
    result = GS._finalizer(state)
    assert "specId" in result
    assert result["specId"].startswith("spec")


def test_finalizer_uses_first_candidate() -> None:
    state = {
        "candidates": [
            {"title": "Game A", "slug": "game-a"},
            {"title": "Game B", "slug": "game-b"},
        ]
    }
    result = GS._finalizer(state)
    assert result["title"] == "Game A"


def test_finalizer_empty_candidates_uses_defaults() -> None:
    state = {"candidates": []}
    result = GS._finalizer(state)
    assert result["title"] == "Untitled"


def test_finalizer_mechanic_json_is_string() -> None:
    state = {"candidates": [{"mechanic": "turn-based"}]}
    result = GS._finalizer(state)
    import json as _json
    parsed = _json.loads(result["mechanicJson"])
    assert parsed["description"] == "turn-based"


def test_finalizer_increments_iterations() -> None:
    state = {"candidates": [{}], "iteration": 2}
    result = GS._finalizer(state)
    assert result["iterations"] == 3


def test_finalizer_budget_defaults_to_100() -> None:
    state = {"candidates": [{}]}
    result = GS._finalizer(state)
    assert result["budgetUsd"] == 100.0


def test_finalizer_preserves_budget_from_candidate() -> None:
    state = {"candidates": [{"budgetUsd": 250.0}]}
    result = GS._finalizer(state)
    assert result["budgetUsd"] == 250.0
