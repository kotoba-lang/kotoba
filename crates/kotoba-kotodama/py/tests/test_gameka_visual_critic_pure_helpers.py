"""Tests for pure helpers in agents/gameka_visual_critic.py:
_scale_perf, _analyze_render, _synthesize, _safe_float, _safe_int."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_agent_gameka_visual_critic"
if _MOD_NAME in sys.modules:
    GVC = sys.modules[_MOD_NAME]
else:
    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    GVC = _load_mod(_MOD_NAME, "kotodama/agents/gameka_visual_critic.py")


# ─── _safe_float / _safe_int ─────────────────────────────────────────────────

def test_gvc_safe_float_in_range() -> None:
    assert GVC._safe_float(0.5, 0.0, 0.0, 1.0) == 0.5


def test_gvc_safe_float_none_returns_default() -> None:
    assert GVC._safe_float(None, 0.3, 0.0, 1.0) == 0.3


def test_gvc_safe_float_clamps_high() -> None:
    assert GVC._safe_float(300.0, 0.0, 0.0, 240.0) == 240.0


def test_gvc_safe_float_clamps_low() -> None:
    assert GVC._safe_float(-5.0, 0.0, 0.0, 1.0) == 0.0


def test_gvc_safe_int_in_range() -> None:
    assert GVC._safe_int(5, 0) == 5


def test_gvc_safe_int_none_returns_default() -> None:
    assert GVC._safe_int(None, 3) == 3


def test_gvc_safe_int_string_numeric() -> None:
    assert GVC._safe_int("7", 0) == 7


def test_gvc_safe_int_invalid_returns_default() -> None:
    assert GVC._safe_int("abc", 99) == 99


# ─── _scale_perf ─────────────────────────────────────────────────────────────

def test_scale_perf_returns_float() -> None:
    result = GVC._scale_perf(55.0, 50.0, 1000)
    assert isinstance(result, float)


def test_scale_perf_good_fps_low_load_near_one() -> None:
    result = GVC._scale_perf(60.0, 58.0, 500)
    assert result >= 0.9


def test_scale_perf_at_target_fps_acceptable() -> None:
    result = GVC._scale_perf(55.0, 50.0, 2000)
    assert result >= 0.5


def test_scale_perf_zero_fps_zero_score() -> None:
    result = GVC._scale_perf(0.0, 0.0, 10000)
    assert result == 0.0


def test_scale_perf_clamped_between_zero_and_one() -> None:
    result = GVC._scale_perf(999.0, 999.0, 0)
    assert 0.0 <= result <= 1.0


def test_scale_perf_floor_fps_gives_low_score() -> None:
    # FPS at floor (25.0) → fps_norm = 0 → only load matters
    result = GVC._scale_perf(GVC.FPS_P50_FLOOR, 0.0, 0)
    assert result <= 0.3  # pure load contribution


def test_scale_perf_high_load_ms_penalises() -> None:
    good_load = GVC._scale_perf(55.0, 50.0, 100)
    bad_load = GVC._scale_perf(55.0, 50.0, 4000)
    assert good_load > bad_load


# ─── _analyze_render ─────────────────────────────────────────────────────────

def test_analyze_render_capture_failed_blocker() -> None:
    state = {
        "captureSucceeded": False,
        "screenshotCids": [],
        "consoleErrorCount": 0,
        "fpsP50": 0.0,
        "sceneLoadMs": 9999,
        "iteration": 0,
    }
    result = GVC._analyze_render(state)
    assert "renderIssues" in result
    assert any(i["severity"] == "blocker" for i in result["renderIssues"])


def test_analyze_render_good_capture_no_blocker() -> None:
    state = {
        "captureSucceeded": True,
        "screenshotCids": ["cid1", "cid2", "cid3"],
        "consoleErrorCount": 0,
        "fpsP50": 60.0,
        "fpsP95": 58.0,
        "sceneLoadMs": 500,
        "iteration": 0,
    }
    result = GVC._analyze_render(state)
    blockers = [i for i in (result.get("renderIssues") or []) if i["severity"] == "blocker"]
    assert blockers == []


def test_analyze_render_render_score_in_state() -> None:
    state = {
        "captureSucceeded": True,
        "screenshotCids": ["c1"],
        "consoleErrorCount": 0,
        "fpsP50": 55.0,
        "fpsP95": 50.0,
        "sceneLoadMs": 1000,
        "iteration": 0,
    }
    result = GVC._analyze_render(state)
    assert "renderScore" in result
    assert 0.0 <= result["renderScore"] <= 1.0


def test_analyze_render_returns_dict() -> None:
    state = {"captureSucceeded": False, "screenshotCids": [], "iteration": 0}
    result = GVC._analyze_render(state)
    assert isinstance(result, dict)


def test_analyze_render_console_errors_add_issue() -> None:
    state = {
        "captureSucceeded": True,
        "screenshotCids": ["c1"],
        "consoleErrorCount": 5,
        "fpsP50": 60.0,
        "sceneLoadMs": 500,
        "iteration": 0,
    }
    result = GVC._analyze_render(state)
    issues = result.get("renderIssues") or []
    error_issues = [i for i in issues if "error" in i.get("category", "")]
    assert len(error_issues) > 0


# ─── _synthesize ─────────────────────────────────────────────────────────────

def _base_synth_state(**kw) -> dict:
    defaults = {
        "renderScore": 0.8,
        "matchScore": 0.8,
        "fpsP50": 60.0,
        "fpsP95": 58.0,
        "sceneLoadMs": 500,
        "renderIssues": [],
        "matchIssues": [],
        "iteration": 0,
    }
    return {**defaults, **kw}


def test_synthesize_pass_when_high_scores_no_issues() -> None:
    result = GVC._synthesize(_base_synth_state())
    assert result["outcome"] == "pass"
    assert result["publish"] is True


def test_synthesize_revise_when_low_score() -> None:
    result = GVC._synthesize(_base_synth_state(renderScore=0.1, matchScore=0.1, iteration=0))
    assert result["outcome"] == "revise"
    assert result["publish"] is False


def test_synthesize_exhausted_at_max_iteration() -> None:
    result = GVC._synthesize(_base_synth_state(
        renderScore=0.1, matchScore=0.1, iteration=GVC.MAX_ITERATION - 1
    ))
    assert result["outcome"] == "exhausted"


def test_synthesize_blocker_prevents_publish() -> None:
    result = GVC._synthesize(_base_synth_state(
        renderScore=1.0, matchScore=1.0,
        renderIssues=[{"severity": "blocker", "category": "render_error", "description": "x"}],
    ))
    assert result["publish"] is False


def test_synthesize_visual_score_is_blend() -> None:
    result = GVC._synthesize(_base_synth_state(renderScore=1.0, matchScore=0.0))
    assert abs(result["visualScore"] - 0.5) < 0.01


def test_synthesize_combined_score_in_state() -> None:
    result = GVC._synthesize(_base_synth_state())
    assert "combinedScore" in result
    assert 0.0 <= result["combinedScore"] <= 1.0


def test_synthesize_perf_score_in_state() -> None:
    result = GVC._synthesize(_base_synth_state())
    assert "perfScore" in result
    assert 0.0 <= result["perfScore"] <= 1.0


def test_synthesize_issues_json_is_string() -> None:
    result = GVC._synthesize(_base_synth_state())
    assert isinstance(result["issuesJson"], str)


def test_synthesize_major_issue_prevents_publish() -> None:
    result = GVC._synthesize(_base_synth_state(
        renderScore=1.0, matchScore=1.0,
        matchIssues=[{"severity": "major", "category": "style", "description": "mismatch"}],
    ))
    assert result["publish"] is False


def test_synthesize_minor_issue_allows_publish() -> None:
    result = GVC._synthesize(_base_synth_state(
        renderScore=1.0, matchScore=1.0,
        renderIssues=[{"severity": "minor", "category": "fps", "description": "slightly low"}],
    ))
    assert result["publish"] is True


# ─── _planner_revise via gameka_studio ───────────────────────────────────────
# (imported through gameka_studio test module)

_GS_MOD_NAME = "_agent_gameka_studio"
if _GS_MOD_NAME in sys.modules:
    _GS = sys.modules[_GS_MOD_NAME]
else:
    def _load_mod2(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    _GS = _load_mod2(_GS_MOD_NAME, "kotodama/agents/gameka_studio.py")


def test_planner_revise_increments_iteration() -> None:
    state = {
        "brief": "A fun platformer",
        "candidates": [],
        "priorSpecs": [],
        "scoreThreshold": 0.8,
        "maxIterations": 5,
        "score": 0.5,
        "iteration": 2,
    }
    result = _GS._planner_revise(state)
    assert result["iteration"] == 3


def test_planner_revise_starts_at_zero() -> None:
    state = {
        "brief": "A fun platformer",
        "candidates": [],
        "priorSpecs": [],
        "scoreThreshold": 0.8,
        "maxIterations": 5,
        "score": 0.0,
        "iteration": 0,
    }
    result = _GS._planner_revise(state)
    assert result["iteration"] == 1


def test_planner_revise_returns_dict() -> None:
    state = {"brief": "x", "candidates": [], "priorSpecs": [], "iteration": 1}
    result = _GS._planner_revise(state)
    assert isinstance(result, dict)


# ─── _analyze_match early-return (renderScore < 0.2 → skip LLM) ──────────────

def test_analyze_match_broken_render_skips_llm() -> None:
    state = {
        "renderScore": 0.1,
        "screenshotUrls": [],
        "title": "Test",
        "genre": "platformer",
        "sceneDescription": "snow",
        "consoleErrorCount": 0,
        "fpsP50": 0.0,
        "iteration": 0,
    }
    result = GVC._analyze_match(state)
    assert result["matchScore"] == 0.0
    assert result["matchIssues"] == []
    assert result["criticModelId"] == "skipped-broken-render"


def test_analyze_match_broken_render_zero_latency() -> None:
    state = {"renderScore": 0.0, "screenshotUrls": [], "title": "x",
             "genre": "puzzle", "sceneDescription": "", "consoleErrorCount": 0, "fpsP50": 0.0}
    result = GVC._analyze_match(state)
    assert result["visualLatencyMs"] == 0


def test_analyze_match_returns_dict() -> None:
    state = {"renderScore": 0.05, "title": "x", "genre": "puzzle",
             "sceneDescription": "", "consoleErrorCount": 0, "fpsP50": 0.0}
    result = GVC._analyze_match(state)
    assert isinstance(result, dict)


def test_analyze_match_preserves_state_fields() -> None:
    state = {
        "renderScore": 0.1,
        "iteration": 2,
        "title": "My Game",
        "screenshotUrls": [],
        "genre": "shmup",
        "sceneDescription": "",
        "consoleErrorCount": 0,
        "fpsP50": 0.0,
    }
    result = GVC._analyze_match(state)
    assert result["iteration"] == 2
    assert result["title"] == "My Game"
