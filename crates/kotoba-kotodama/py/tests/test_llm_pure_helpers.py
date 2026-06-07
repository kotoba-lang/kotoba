"""Tests for pure helper functions in kotodama.llm."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama import llm


# ─── _strip_code_fence ───────────────────────────────────────────────────────

def test_strip_fence_passthrough_plain_json() -> None:
    text = '{"key": "value"}'
    assert llm._strip_code_fence(text) == text


def test_strip_fence_removes_json_fence() -> None:
    text = "```json\n{\"key\": \"value\"}\n```"
    result = llm._strip_code_fence(text)
    assert result == '{"key": "value"}'


def test_strip_fence_removes_plain_fence() -> None:
    text = "```\n{\"key\": \"value\"}\n```"
    result = llm._strip_code_fence(text)
    assert result == '{"key": "value"}'


def test_strip_fence_handles_open_only_fence() -> None:
    text = "```\n{\"key\": \"value\"}"
    result = llm._strip_code_fence(text)
    assert '{"key": "value"}' in result


def test_strip_fence_handles_pathological_no_body() -> None:
    text = "```"
    result = llm._strip_code_fence(text)
    assert result == "```"


def test_strip_fence_strips_surrounding_whitespace() -> None:
    text = "  ```json\n{\"a\": 1}\n```  "
    result = llm._strip_code_fence(text)
    assert result == '{"a": 1}'


# ─── _extract_first_json_object ──────────────────────────────────────────────

def test_extract_first_json_finds_object() -> None:
    text = 'Some preamble {"key": "value"} trailing text'
    result = llm._extract_first_json_object(text)
    assert result == {"key": "value"}


def test_extract_first_json_nested_object() -> None:
    text = '{"outer": {"inner": 42}}'
    result = llm._extract_first_json_object(text)
    assert result == {"outer": {"inner": 42}}


def test_extract_first_json_no_object_returns_none() -> None:
    assert llm._extract_first_json_object("no json here") is None
    assert llm._extract_first_json_object("") is None


def test_extract_first_json_invalid_json_returns_none() -> None:
    assert llm._extract_first_json_object("{not valid json}") is None


def test_extract_first_json_handles_prose_preamble() -> None:
    text = 'The result is: {"branch": "fast", "confidence": 0.9}'
    result = llm._extract_first_json_object(text)
    assert result is not None
    assert result["branch"] == "fast"
    assert result["confidence"] == 0.9


# ─── parse_json_content ──────────────────────────────────────────────────────

def test_parse_json_content_none_returns_none() -> None:
    assert llm.parse_json_content(None) is None


def test_parse_json_content_empty_returns_none() -> None:
    assert llm.parse_json_content("") is None


def test_parse_json_content_valid_json() -> None:
    result = llm.parse_json_content('{"ok": true, "score": 0.8}')
    assert result == {"ok": True, "score": 0.8}


def test_parse_json_content_strips_fence_then_parses() -> None:
    text = "```json\n{\"branch\": \"fast\"}\n```"
    result = llm.parse_json_content(text)
    assert result == {"branch": "fast"}


def test_parse_json_content_falls_back_to_extract() -> None:
    text = "The model says: {\"answer\": 42}"
    result = llm.parse_json_content(text)
    assert result is not None
    assert result["answer"] == 42


def test_parse_json_content_garbage_returns_none() -> None:
    result = llm.parse_json_content("totally not json at all")
    assert result is None


# ─── resolve_model ───────────────────────────────────────────────────────────

def test_resolve_model_known_tier() -> None:
    model = llm.resolve_model("fast")
    assert isinstance(model, str)
    assert len(model) > 0


def test_resolve_model_hf_style_passthrough() -> None:
    model_id = "Qwen/Qwen2.5-7B-Instruct"
    assert llm.resolve_model(model_id) == model_id


def test_resolve_model_unknown_tier_raises() -> None:
    try:
        llm.resolve_model("nonexistent-tier-xyz")
        assert False, "expected LlmError"
    except llm.LlmError:
        pass


def test_resolve_model_all_standard_tiers() -> None:
    for tier in ("fast", "mid", "classifier", "structured", "deep"):
        model = llm.resolve_model(tier)
        assert isinstance(model, str) and model
