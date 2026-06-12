"""Tests for pure helper functions in projector.py and science_knowledge.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import projector as P
from kotodama.primitives import science_knowledge as SK


# ─── projector: _strip_reasoning ─────────────────────────────────────────────

def test_strip_reasoning_no_tag_returns_empty_reasoning() -> None:
    reasoning, cleaned = P._strip_reasoning("Hello world")
    assert reasoning == ""
    assert cleaned == "Hello world"


def test_strip_reasoning_extracts_tag() -> None:
    text = "<reasoning>Think step by step</reasoning>Final answer"
    reasoning, cleaned = P._strip_reasoning(text)
    assert reasoning == "Think step by step"
    assert "reasoning" not in cleaned
    assert "Final answer" in cleaned


def test_strip_reasoning_empty_string() -> None:
    reasoning, cleaned = P._strip_reasoning("")
    assert reasoning == ""
    assert cleaned == ""


def test_strip_reasoning_none_safe() -> None:
    reasoning, cleaned = P._strip_reasoning(None)
    assert reasoning == ""


def test_strip_reasoning_multiline_tag() -> None:
    text = "<reasoning>\nline1\nline2\n</reasoning>done"
    reasoning, cleaned = P._strip_reasoning(text)
    assert "line1" in reasoning
    assert "line2" in reasoning
    assert cleaned.strip() == "done"


# ─── projector: _extract_final_answer ────────────────────────────────────────

def test_extract_final_answer_with_tag() -> None:
    text = "Some reasoning <answer>The final answer is X</answer>"
    result = P._extract_final_answer(text)
    assert result == "The final answer is X"


def test_extract_final_answer_no_tag_returns_full() -> None:
    text = "No answer tag here"
    result = P._extract_final_answer(text)
    assert result == "No answer tag here"


def test_extract_final_answer_empty_string() -> None:
    result = P._extract_final_answer("")
    assert result == ""


def test_extract_final_answer_none_safe() -> None:
    result = P._extract_final_answer(None)
    assert result == ""


# ─── projector: _format_tools_for_prompt ─────────────────────────────────────

def test_format_tools_empty_returns_none_marker() -> None:
    result = P._format_tools_for_prompt([])
    assert result == "(none)"


def test_format_tools_single_tool() -> None:
    tools = [{"name": "search", "description": "Search the web", "schema": {"q": "string"}}]
    result = P._format_tools_for_prompt(tools)
    assert "search" in result
    assert "Search the web" in result
    assert "ARGS=" in result


def test_format_tools_multiple_tools() -> None:
    tools = [
        {"name": "search", "description": "Search"},
        {"name": "read", "description": "Read file"},
    ]
    result = P._format_tools_for_prompt(tools)
    assert "search" in result
    assert "read" in result
    lines = result.strip().split("\n")
    assert len(lines) == 2


def test_format_tools_invalid_schema_graceful() -> None:
    tools = [{"name": "bad", "description": "x", "schema": None}]
    result = P._format_tools_for_prompt(tools)
    assert "bad" in result


# ─── projector: _parse_tool_calls ────────────────────────────────────────────

def test_parse_tool_calls_no_calls_returns_empty() -> None:
    result = P._parse_tool_calls("No tool calls here")
    assert result == []


def test_parse_tool_calls_empty_string() -> None:
    assert P._parse_tool_calls("") == []


def test_parse_tool_calls_finds_call() -> None:
    text = '[TOOL_CALL: search({"q": "hello"})]'
    result = P._parse_tool_calls(text)
    assert len(result) == 1
    name, args = result[0]
    assert name == "search"
    assert args == {"q": "hello"}


def test_parse_tool_calls_empty_args() -> None:
    text = "[TOOL_CALL: ping({})]"
    result = P._parse_tool_calls(text)
    assert len(result) == 1
    name, args = result[0]
    assert name == "ping"
    assert args == {}


def test_parse_tool_calls_invalid_json_gives_empty_args() -> None:
    text = "[TOOL_CALL: bad({not: valid})]"
    result = P._parse_tool_calls(text)
    # If the regex doesn't match or JSON fails, args should be {}
    if result:
        _, args = result[0]
        assert args == {}


# ─── projector: _guardrail_check ─────────────────────────────────────────────

def test_guardrail_check_allows_normal_text() -> None:
    result = P._guardrail_check("Hello, how can I help?")
    assert result["ok"] is True


def test_guardrail_check_blocks_rm_rf() -> None:
    result = P._guardrail_check("run rm -rf /")
    assert result["ok"] is False
    assert "policy_block" in result["reason"]


def test_guardrail_check_blocks_drop_table() -> None:
    result = P._guardrail_check("DROP TABLE vertex_actor")
    assert result["ok"] is False


def test_guardrail_check_blocks_delete_vertex() -> None:
    result = P._guardrail_check("DELETE FROM vertex_actor WHERE 1=1")
    assert result["ok"] is False


def test_guardrail_check_empty_string_allowed() -> None:
    result = P._guardrail_check("")
    assert result["ok"] is True


def test_guardrail_check_none_safe() -> None:
    result = P._guardrail_check(None)
    assert result["ok"] is True


# ─── projector: _build_system_prompt ─────────────────────────────────────────

def test_build_system_prompt_basic() -> None:
    state = {}
    result = P._build_system_prompt(state)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_system_prompt_includes_tools() -> None:
    state = {"memberTools": [{"name": "search", "description": "Search", "schema": {}}]}
    result = P._build_system_prompt(state)
    assert "search" in result


def test_build_system_prompt_includes_memory() -> None:
    state = {"reflexionMemory": [{"lesson": "Always verify data before returning"}]}
    result = P._build_system_prompt(state)
    assert "Always verify data" in result


def test_build_system_prompt_limits_memory_to_5() -> None:
    state = {
        "reflexionMemory": [{"lesson": f"lesson-{i}"} for i in range(10)]
    }
    result = P._build_system_prompt(state)
    # Only last 5 should appear
    assert "lesson-9" in result
    assert "lesson-4" not in result


# ─── science_knowledge: _vid ─────────────────────────────────────────────────

def test_vid_format() -> None:
    vid = SK._vid("sciKnowledge", "periodicElement", "H")
    assert vid.startswith("at://did:web:sciKnowledge.etzhayyim.com/")
    assert "com.etzhayyim.apps.sciKnowledge.periodicElement" in vid
    assert vid.endswith("/H")


def test_vid_deterministic() -> None:
    a = SK._vid("actor", "collection", "rkey")
    b = SK._vid("actor", "collection", "rkey")
    assert a == b


def test_vid_varies_by_rkey() -> None:
    a = SK._vid("actor", "col", "rkey1")
    b = SK._vid("actor", "col", "rkey2")
    assert a != b


# ─── science_knowledge: _edge_id ─────────────────────────────────────────────

def test_edge_id_deterministic() -> None:
    a = SK._edge_id("part1", "part2")
    b = SK._edge_id("part1", "part2")
    assert a == b


def test_edge_id_varies_with_parts() -> None:
    a = SK._edge_id("x", "y")
    b = SK._edge_id("x", "z")
    assert a != b


def test_edge_id_length() -> None:
    eid = SK._edge_id("src", "dst")
    assert len(eid) == 24


def test_edge_id_hex_chars() -> None:
    eid = SK._edge_id("src", "dst")
    assert all(c in "0123456789abcdef" for c in eid)
