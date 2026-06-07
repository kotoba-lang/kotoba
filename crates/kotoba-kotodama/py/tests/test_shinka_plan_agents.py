"""Tests for shinka handler (input parsing) and plan agent pure functions."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load_handler(name: str) -> types.ModuleType:
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    mod_name = f"_hshinka_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_agent(name: str) -> types.ModuleType:
    src = _py_src / "kotodama" / "agents" / f"{name}.py"
    mod_name = f"_agent_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─── shinka handler ───────────────────────────────────────────────────────────

SH = _load_handler("shinka")


def test_shinka_tick_actor_empty_input_returns_error():
    out = json.loads(SH.tick_actor(""))
    assert "error" in out
    assert "actorDid" in out["error"]


def test_shinka_tick_actor_invalid_json_returns_error():
    out = json.loads(SH.tick_actor("{not-valid-json"))
    assert "error" in out
    assert "invalid JSON" in out["error"]


def test_shinka_tick_actor_missing_actor_did_returns_error():
    out = json.loads(SH.tick_actor("{}"))
    assert "error" in out
    assert "actorDid" in out["error"]


def test_shinka_tick_actor_non_did_string_returns_error():
    out = json.loads(SH.tick_actor("not-a-did"))
    assert "error" in out


def test_shinka_tick_actor_bare_did_calls_run_tick():
    with patch.object(SH, "run_tick", return_value={"ok": True, "actor": "test"}) as mock_rt:
        out = json.loads(SH.tick_actor("did:web:test.etzhayyim.com"))
    mock_rt.assert_called_once_with("did:web:test.etzhayyim.com")
    assert out["ok"] is True


def test_shinka_tick_actor_json_wrapped_did_calls_run_tick():
    with patch.object(SH, "run_tick", return_value={"ok": True}) as mock_rt:
        out = json.loads(SH.tick_actor(json.dumps({"actorDid": "did:plc:abcdef123456"})))
    mock_rt.assert_called_once_with("did:plc:abcdef123456")
    assert out["ok"] is True


def test_shinka_tick_actor_snake_case_actor_did():
    with patch.object(SH, "run_tick", return_value={"ticked": True}) as mock_rt:
        out = json.loads(SH.tick_actor(json.dumps({"actor_did": "did:web:shinshi.etzhayyim.com"})))
    mock_rt.assert_called_once_with("did:web:shinshi.etzhayyim.com")
    assert out["ticked"] is True


def test_shinka_tick_actor_whitespace_stripped():
    with patch.object(SH, "run_tick", return_value={"ok": True}) as mock_rt:
        SH.tick_actor("  did:web:test.etzhayyim.com  ")
    mock_rt.assert_called_once_with("did:web:test.etzhayyim.com")


# ─── plan agent pure functions ────────────────────────────────────────────────

# Load the plan agent module (langgraph stub installed by conftest)
PA = _load_agent("plan")


def test_plan_summarise_plan_is_identity():
    state = {"branch": "fast", "confidence": 0.8, "reason": "quick"}
    result = PA._summarise_plan(state)
    assert result is state


def test_plan_summarise_plan_empty_state():
    assert PA._summarise_plan({}) == {}


def test_plan_classify_task_llm_success():
    fake_result = {
        "ok": True,
        "data": {
            "branch": "thorough",
            "nextTool": "com.etzhayyim.apps.yabai.trackPhishingInfra",
            "confidence": 0.9,
            "reason": "Complex entity requires deep analysis",
        },
        "model": "test-model",
    }
    with patch.object(PA.llm, "call_tier_json", return_value=fake_result):
        out = PA._classify_task({"context": {"type": "entity"}, "taskHint": "classify"})
    assert out["branch"] == "thorough"
    assert out["confidence"] == 0.9
    assert out["nextTool"] == "com.etzhayyim.apps.yabai.trackPhishingInfra"
    assert out["llmModel"] == "test-model"


def test_plan_classify_task_llm_failure_defaults_to_fast():
    fake_result = {"ok": False, "error": "rate-limited", "model": ""}
    with patch.object(PA.llm, "call_tier_json", return_value=fake_result):
        out = PA._classify_task({"context": {}})
    assert out["branch"] == "fast"
    assert out["confidence"] == 0.0
    assert "llm-error" in out["reason"]


def test_plan_classify_task_invalid_branch_defaults_to_fast():
    fake_result = {
        "ok": True,
        "data": {"branch": "unknown-branch", "nextTool": "", "confidence": 0.5, "reason": "x"},
        "model": "",
    }
    with patch.object(PA.llm, "call_tier_json", return_value=fake_result):
        out = PA._classify_task({})
    assert out["branch"] == "fast"


def test_plan_classify_task_skip_branch():
    fake_result = {
        "ok": True,
        "data": {"branch": "skip", "nextTool": "", "confidence": 0.7, "reason": "already processed"},
        "model": "m",
    }
    with patch.object(PA.llm, "call_tier_json", return_value=fake_result):
        out = PA._classify_task({})
    assert out["branch"] == "skip"


def test_plan_classify_task_confidence_clamped():
    fake_result = {
        "ok": True,
        "data": {"branch": "fast", "nextTool": "", "confidence": 999.0, "reason": "x"},
        "model": "",
    }
    with patch.object(PA.llm, "call_tier_json", return_value=fake_result):
        out = PA._classify_task({})
    assert out["confidence"] <= 1.0


def test_plan_classify_task_reason_truncated():
    long_reason = "a" * 500
    fake_result = {
        "ok": True,
        "data": {"branch": "fast", "nextTool": "", "confidence": 0.5, "reason": long_reason},
        "model": "",
    }
    with patch.object(PA.llm, "call_tier_json", return_value=fake_result):
        out = PA._classify_task({})
    assert len(out["reason"]) <= 200


def test_plan_audit_plan_db_failure_returns_empty_rkey():
    state = {"branch": "fast", "nextTool": "", "confidence": 0.5, "reason": "x"}
    with patch("kotodama.db_sync.sync_cursor", side_effect=Exception("DB down")):
        out = PA._audit_plan(state)
    assert out["auditRkey"] == ""


def test_plan_audit_plan_success_returns_rkey():
    state = {"branch": "thorough", "nextTool": "com.etzhayyim.foo", "confidence": 0.8, "reason": "ok"}
    mock_cur = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cur)
    mock_cm.__exit__ = MagicMock(return_value=False)
    with patch.object(PA, "sync_cursor", return_value=mock_cm):
        out = PA._audit_plan(state)
    assert out["auditRkey"].startswith("plan-")


def test_plan_full_graph_llm_mock():
    fake_result = {
        "ok": True,
        "data": {"branch": "fast", "nextTool": "", "confidence": 0.6, "reason": "quick"},
        "model": "m",
    }
    mock_cur = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cur)
    mock_cm.__exit__ = MagicMock(return_value=False)
    with (
        patch.object(PA.llm, "call_tier_json", return_value=fake_result),
        patch.object(PA, "sync_cursor", return_value=mock_cm),
    ):
        out = asyncio.run(PA.task_agent_plan(context={"key": "val"}, taskHint="test"))
    assert out["branch"] == "fast"
    assert out["confidence"] == 0.6
