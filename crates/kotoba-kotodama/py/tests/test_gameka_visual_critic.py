"""
Offline unit tests for gameka.visualCritic — exercises the visual-test
QA loop logic against stubbed LLM responses. Same offline pattern as
test_gameka_codegen.py.

Coverage:
  - degraded mode (LLM unavailable) still produces a usable score
  - render score floors out on broken capture / many console errors
  - publish gate honours blocker severity even at high score
  - outcome ladder: pass | revise | exhausted (iteration boundary)
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
import types
from pathlib import Path as _P

ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"


def _load(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _install_llm_stub(payload: dict | None, ok: bool = True) -> list:
    """Stub kotodama.llm. payload=None + ok=False = degraded path."""
    calls: list[dict] = []
    stub = types.ModuleType("kotodama.llm")

    def call_tier_json(tier, system="", user="", max_tokens=0, temperature=0.0):
        calls.append({"tier": tier})
        if not ok:
            return {"ok": False, "error": "no-vision-tier", "model": ""}
        return {"ok": True, "data": payload or {}, "model": "stub-vision"}

    stub.call_tier_json = call_tier_json
    sys.modules["kotodama.llm"] = stub
    if "kotodama" not in sys.modules:
        sys.modules["kotodama"] = types.ModuleType("kotodama")
    sys.modules["kotodama"].llm = stub  # type: ignore[attr-defined]
    return calls


def _try_load_critic():
    try:
        import langgraph  # noqa: F401
    except ImportError:  # pragma: no cover
        import pytest

        pytest.skip("langgraph not installed in test venv")
    return _load("_gameka_visual_critic", "agents/gameka_visual_critic.py")


# ─── render-score primitives (no LangGraph) ─────────────────────────────


def test_render_score_perfect_signals():
    crit = _try_load_critic()
    out = crit._analyze_render({
        "captureSucceeded": True,
        "screenshotCids": ["a", "b", "c"],
        "consoleErrorCount": 0,
        "fpsP50": 60.0,
        "sceneLoadMs": 1500,
    })
    assert out["renderScore"] == 1.0
    assert out["renderIssues"] == []


def test_render_score_blocker_on_capture_failure():
    crit = _try_load_critic()
    out = crit._analyze_render({
        "captureSucceeded": False,
        "screenshotCids": [],
        "consoleErrorCount": 0,
        "fpsP50": 0.0,
        "sceneLoadMs": 0,
    })
    assert out["renderScore"] == 0.0
    sevs = {i["severity"] for i in out["renderIssues"]}
    assert "blocker" in sevs


def test_render_score_major_on_partial_capture():
    crit = _try_load_critic()
    out = crit._analyze_render({
        "captureSucceeded": True,
        "screenshotCids": ["a"],   # only 1 of 3
        "consoleErrorCount": 0,
        "fpsP50": 60.0,
        "sceneLoadMs": 1500,
    })
    assert out["renderScore"] <= 0.4
    assert any(i["severity"] == "major" for i in out["renderIssues"])


def test_render_score_blocker_on_5plus_console_errors():
    crit = _try_load_critic()
    out = crit._analyze_render({
        "captureSucceeded": True,
        "screenshotCids": ["a", "b", "c"],
        "consoleErrorCount": 7,
        "fpsP50": 60.0,
        "sceneLoadMs": 1500,
    })
    assert out["renderScore"] <= 0.2
    assert any(i["severity"] == "blocker" for i in out["renderIssues"])


# ─── perf scaling (pure function) ───────────────────────────────────────


def test_perf_score_linear():
    crit = _try_load_critic()
    # at fps_p50=FPS_P50_TARGET (55) and load=0 → ~1.0
    s = crit._scale_perf(crit.FPS_P50_TARGET, crit.FPS_P50_TARGET, 0)
    assert s >= 0.9
    # at fps_p50=FPS_P50_FLOOR (25) and load=budget → ~0.0
    s = crit._scale_perf(crit.FPS_P50_FLOOR, crit.FPS_P50_FLOOR, crit.SCENE_LOAD_BUDGET_MS)
    assert s <= 0.1


# ─── full loop end-to-end (stubbed LLM) ─────────────────────────────────


def _run(critic, **kwargs):
    import asyncio
    return asyncio.run(
        critic.task_agent_gameka_visual_critic(**kwargs)
    )


def test_full_pass_outcome():
    _install_llm_stub({"matchScore": 0.9, "issues": [], "rationale": "tight"})
    crit = _try_load_critic()
    out = _run(crit,
        specId="s", artifactId="a", iteration=0,
        sceneDescription="quarry biome", genre="rogue-lite",
        title="Q", slug="q",
        screenshotCids=["c1", "c2", "c3"], screenshotUrls=["u1", "u2", "u3"],
        consoleErrorCount=0, fpsP50=60.0, fpsP95=58.0, sceneLoadMs=1500,
        captureSucceeded=True,
    )
    assert out["publish"] is True
    assert out["outcome"] == "pass"
    assert out["combinedScore"] >= 0.7
    assert out["criticModelId"] == "stub-vision"


def test_revise_outcome_when_iteration_remaining():
    _install_llm_stub({
        "matchScore": 0.3,
        "issues": [{"category": "scene_mismatch", "severity": "major", "description": "wrong biome"}],
        "rationale": "off",
    })
    crit = _try_load_critic()
    out = _run(crit,
        specId="s", artifactId="a", iteration=0,   # 0 of 3
        sceneDescription="quarry", genre="puzzle", title="X", slug="x",
        screenshotCids=["c1", "c2", "c3"], screenshotUrls=["u1"],
        consoleErrorCount=0, fpsP50=60.0, fpsP95=58.0, sceneLoadMs=1500,
        captureSucceeded=True,
    )
    assert out["publish"] is False
    assert out["outcome"] == "revise"
    issues = json.loads(out["issuesJson"])
    assert any(i["severity"] == "major" for i in issues)


def test_exhausted_outcome_at_max_iteration():
    # major issue forces publish=False so the exhausted path triggers
    _install_llm_stub({"matchScore": 0.3, "issues": [{"category": "scene_mismatch", "severity": "major", "description": "wrong biome"}], "rationale": "off"})
    crit = _try_load_critic()
    out = _run(crit,
        specId="s", artifactId="a", iteration=2,   # next would be 3 = MAX
        sceneDescription="x", genre="puzzle", title="X", slug="x",
        screenshotCids=["c1", "c2", "c3"], screenshotUrls=["u1"],
        consoleErrorCount=0, fpsP50=60.0, fpsP95=58.0, sceneLoadMs=1500,
        captureSucceeded=True,
    )
    assert out["publish"] is False
    assert out["outcome"] == "exhausted"


def test_blocker_severity_blocks_publish_even_at_high_score():
    # Render gives a blocker (no capture), match LLM still scores high
    # — combined score might pass threshold but blocker forces publish=false.
    _install_llm_stub({"matchScore": 1.0, "issues": [], "rationale": "looks good"})
    crit = _try_load_critic()
    out = _run(crit,
        specId="s", artifactId="a", iteration=0,
        sceneDescription="x", genre="puzzle", title="X", slug="x",
        screenshotCids=[], screenshotUrls=[],
        consoleErrorCount=0, fpsP50=60.0, fpsP95=58.0, sceneLoadMs=1500,
        captureSucceeded=False,   # ← blocker source
    )
    assert out["publish"] is False
    assert out["outcome"] in ("revise", "exhausted")
    issues = json.loads(out["issuesJson"])
    assert any(i["severity"] == "blocker" for i in issues)


def test_degraded_mode_when_llm_unavailable():
    _install_llm_stub(None, ok=False)
    crit = _try_load_critic()
    out = _run(crit,
        specId="s", artifactId="a", iteration=0,
        sceneDescription="quarry", genre="puzzle", title="X", slug="x",
        screenshotCids=["c1", "c2", "c3"], screenshotUrls=["u1", "u2", "u3"],
        consoleErrorCount=0, fpsP50=60.0, fpsP95=58.0, sceneLoadMs=1500,
        captureSucceeded=True,
    )
    # Render score is perfect, perf score is high, match defaults to 0.5
    # → combined ~ 0.7*0.75 + 0.3*~0.9 = ~0.79 → pass
    assert out["criticModelId"] == "degraded-no-vision"
    issues = json.loads(out["issuesJson"])
    assert any(i["category"] == "art_quality" and "degraded" in i["description"] for i in issues)


def test_skipped_when_render_already_broken():
    """Render score < 0.2 short-circuits the LLM — no point asking
    "is this a good game?" if the canvas is empty."""
    calls = _install_llm_stub({"matchScore": 1.0, "issues": []})
    crit = _try_load_critic()
    out = _run(crit,
        specId="s", artifactId="a", iteration=0,
        sceneDescription="x", genre="puzzle", title="X", slug="x",
        screenshotCids=[], screenshotUrls=[],
        consoleErrorCount=0, fpsP50=60.0, fpsP95=58.0, sceneLoadMs=1500,
        captureSucceeded=False,
    )
    assert out["criticModelId"] == "skipped-broken-render"
    assert calls == []   # LLM never invoked
    assert out["publish"] is False
