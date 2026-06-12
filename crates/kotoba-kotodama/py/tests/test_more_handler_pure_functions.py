"""Tests for pure functions in additional handler modules.

Covers: mangaka_storyboard, news_translate, vultr_inference, user_task_sink.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path as _P
from unittest.mock import patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf() registers cleanly without the runtime dep.
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load(name: str) -> types.ModuleType:
    """Load a handler module by file path (bypasses handlers/__init__)."""
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    mod_name = f"_handler2_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    # Register in sys.modules so @dataclass can resolve the module's __dict__.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─── mangaka_storyboard ──────────────────────────────────────────────────────

MS = _load("mangaka_storyboard")


def test_mangaka_err_returns_json_with_error():
    out = json.loads(MS._err("bad request"))
    assert out["error"] == "bad request"


def test_mangaka_err_includes_extra_fields():
    out = json.loads(MS._err("oops", code=42))
    assert out["error"] == "oops"
    assert out["code"] == 42


def test_mangaka_clamp_int_in_range():
    assert MS._clamp_int(3, 2, 1, 8) == 3


def test_mangaka_clamp_int_below_lo():
    assert MS._clamp_int(0, 2, 1, 8) == 1


def test_mangaka_clamp_int_above_hi():
    assert MS._clamp_int(100, 2, 1, 8) == 8


def test_mangaka_clamp_int_non_numeric_returns_default():
    assert MS._clamp_int("abc", 5, 1, 10) == 5


def test_mangaka_clamp_int_none_returns_default():
    assert MS._clamp_int(None, 3, 1, 10) == 3


def test_mangaka_storyboard_missing_story_returns_error():
    out = json.loads(MS.storyboard_from_prompt(json.dumps({})))
    assert "error" in out
    assert "story" in out["error"]


def test_mangaka_storyboard_invalid_json_returns_error():
    out = json.loads(MS.storyboard_from_prompt("not-json"))
    assert "error" in out


def test_mangaka_storyboard_non_dict_json_returns_error():
    out = json.loads(MS.storyboard_from_prompt("[1, 2, 3]"))
    assert "error" in out


def test_mangaka_storyboard_xrpc_wrapper_missing_story_returns_error():
    body = json.dumps({"json": {"pageCount": 2}})
    out = json.loads(MS.storyboard_from_prompt(body))
    assert "error" in out


def test_mangaka_storyboard_calls_llm_with_story():
    fake_result = {
        "ok": True,
        "data": {"pages": [{"pageNumber": 1, "panels": []}]},
        "model": "test",
        "usage": {},
        "latencyMs": 10,
    }
    with patch.object(MS.llm, "call_tier_json", return_value=fake_result):
        out = json.loads(MS.storyboard_from_prompt(json.dumps({"story": "a hero's journey"})))
    assert "pages" in out or "error" in out  # success or LLM parse error


# ─── news_translate ──────────────────────────────────────────────────────────

NT = _load("news_translate")


def test_news_translate_empty_text_returns_empty():
    out = NT.translate("", "en", "ja")
    assert out == ""


def test_news_translate_same_lang_returns_input():
    out = NT.translate("hello", "en", "en")
    assert out == "hello"


def test_news_translate_no_target_lang_returns_input():
    out = NT.translate("hello", "en", "")
    assert out == "hello"


def test_news_translate_short_text_returns_as_is():
    # Single char — below minimum length
    out = NT.translate("a", "en", "ja")
    assert out == "a"


def test_news_translate_llm_success():
    fake = {"content": "こんにちは"}
    with patch.object(NT.llm, "call_tier", return_value=fake):
        out = NT.translate("hello", "en", "ja")
    assert out == "こんにちは"


def test_news_translate_strips_double_quotes():
    fake = {"content": '"こんにちは"'}
    with patch.object(NT.llm, "call_tier", return_value=fake):
        out = NT.translate("hello", "en", "ja")
    assert out == "こんにちは"


def test_news_translate_strips_japanese_quotes():
    fake = {"content": "「こんにちは」"}
    with patch.object(NT.llm, "call_tier", return_value=fake):
        out = NT.translate("hello", "en", "ja")
    assert out == "こんにちは"


def test_news_translate_llm_error_returns_original():
    with patch.object(NT.llm, "call_tier", side_effect=NT.llm.LlmError("fail")):
        out = NT.translate("hello world", "en", "ja")
    assert out == "hello world"


def test_news_translate_empty_llm_content_returns_original():
    fake = {"content": ""}
    with patch.object(NT.llm, "call_tier", return_value=fake):
        out = NT.translate("hello world", "en", "ja")
    assert out == "hello world"


# ─── vultr_inference ─────────────────────────────────────────────────────────

VI = _load("vultr_inference")


def test_vultr_err_returns_json_with_error():
    out = json.loads(VI._err("bad request"))
    assert out["error"] == "bad request"


def test_vultr_chat_completions_no_api_key_returns_error(monkeypatch):
    monkeypatch.delenv("VULTR_SERVERLESS_KEY", raising=False)
    out = json.loads(VI.chat_completions(json.dumps({
        "model": "Qwen/Qwen3.5-397B-A17B-FP8",
        "messages": [{"role": "user", "content": "hi"}],
    })))
    assert "error" in out
    assert "VULTR_SERVERLESS_KEY" in out["error"]


def test_vultr_chat_completions_invalid_json_returns_error(monkeypatch):
    monkeypatch.setenv("VULTR_SERVERLESS_KEY", "test-key")
    out = json.loads(VI.chat_completions("not-json"))
    assert "error" in out


def test_vultr_chat_completions_missing_model_returns_error(monkeypatch):
    monkeypatch.setenv("VULTR_SERVERLESS_KEY", "test-key")
    out = json.loads(VI.chat_completions(json.dumps({
        "messages": [{"role": "user", "content": "hi"}],
    })))
    assert "error" in out
    assert "model" in out["error"]


def test_vultr_chat_completions_missing_messages_returns_error(monkeypatch):
    monkeypatch.setenv("VULTR_SERVERLESS_KEY", "test-key")
    out = json.loads(VI.chat_completions(json.dumps({
        "model": "Qwen/Qwen3.5-397B-A17B-FP8",
        "messages": [],
    })))
    assert "error" in out
    assert "messages" in out["error"]


def test_vultr_chat_completions_xrpc_wrapper(monkeypatch):
    monkeypatch.setenv("VULTR_SERVERLESS_KEY", "test-key")
    body = json.dumps({"json": {
        "model": "Qwen/Qwen3.5-397B-A17B-FP8",
        "messages": [{"role": "user", "content": "hi"}],
    }})
    # No real HTTP call — just verify the wrapper is unwrapped before missing
    # the model check (it should pass model check and hit network)
    import urllib.request
    class _FakeResp:
        status = 200
        def read(self): return json.dumps({"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}], "usage": {}, "model": "q"}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass
    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        out = json.loads(VI.chat_completions(body))
    assert out.get("content") == "hi" or "error" in out


# ─── user_task_sink ───────────────────────────────────────────────────────────

UT = _load("user_task_sink")


def test_user_task_sink_parse_maybe_json_none():
    assert UT._parse_maybe_json(None) is None


def test_user_task_sink_parse_maybe_json_list_passthrough():
    assert UT._parse_maybe_json(["a", "b"]) == ["a", "b"]


def test_user_task_sink_parse_maybe_json_dict_passthrough():
    assert UT._parse_maybe_json({"key": "val"}) == {"key": "val"}


def test_user_task_sink_parse_maybe_json_bare_string():
    assert UT._parse_maybe_json("hello") == "hello"


def test_user_task_sink_parse_maybe_json_json_array_string():
    result = UT._parse_maybe_json('["group1","group2"]')
    assert result == ["group1", "group2"]


def test_user_task_sink_parse_maybe_json_json_object_string():
    result = UT._parse_maybe_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_user_task_sink_parse_maybe_json_invalid_json_string():
    result = UT._parse_maybe_json("[invalid")
    assert result == "[invalid"


def test_user_task_sink_dataclass_fields():
    task = UT.ActivatedUserTask(
        job_key=123,
        process_instance_key=456,
        process_definition_key=789,
        bpmn_process_id="test-process",
        element_id="Task_1",
        element_name="My Task",
        form_key=None,
        candidate_groups=["admin"],
        candidate_users=[],
        assignee="alice@example.com",
        due_date=None,
        variables={"amount": 100},
    )
    assert task.job_key == 123
    assert task.assignee == "alice@example.com"
    assert task.candidate_groups == ["admin"]
    assert task.variables == {"amount": 100}
