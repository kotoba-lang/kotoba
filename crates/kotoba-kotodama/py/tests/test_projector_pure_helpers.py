"""Tests for pure helper functions in primitives/projector.py.

Only functions that do no DB/LLM/network I/O are tested here:
  _strip_reasoning, _extract_final_answer,
  task_projector_command_parse, task_projector_command_deferred,
  _format_tools_for_prompt, _parse_tool_calls, _guardrail_check

Uses isolated module load + stubs so no real DB or LLM connections are made.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub kotodama.llm and kotodama.db_sync before importing projector
_llm_stub = types.ModuleType("kotodama.llm")
_llm_stub.call_tier = lambda *a, **kw: {"content": "", "model": "", "usage": {}}  # type: ignore[attr-defined]
_llm_stub.call_tier_json = lambda *a, **kw: {"ok": False, "error": "stub"}  # type: ignore[attr-defined]
_llm_stub.LlmError = type("LlmError", (Exception,), {})  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.llm", _llm_stub)

_db_stub = types.ModuleType("kotodama.db_sync")
def _fake_sync_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()
_db_stub.sync_cursor = _fake_sync_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)

# Ensure kotodama package stub exists
_pkg_stub = types.ModuleType("kotodama")
sys.modules.setdefault("kotodama", _pkg_stub)


_MOD_NAME = "_projector_pure_helpers"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "projector.py"
    _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

P = sys.modules[_MOD_NAME]


# ─── _strip_reasoning ────────────────────────────────────────────────────────

def test_strip_reasoning_extracts_content() -> None:
    reasoning, reply = P._strip_reasoning("<reasoning>think hard</reasoning>answer")
    assert reasoning == "think hard"


def test_strip_reasoning_cleans_tag_from_reply() -> None:
    _, reply = P._strip_reasoning("<reasoning>x</reasoning>final answer")
    assert "<reasoning>" not in reply
    assert "final answer" in reply


def test_strip_reasoning_no_tag_returns_empty_reasoning() -> None:
    reasoning, reply = P._strip_reasoning("plain text")
    assert reasoning == ""


def test_strip_reasoning_no_tag_preserves_text() -> None:
    _, reply = P._strip_reasoning("plain text")
    assert reply == "plain text"


def test_strip_reasoning_empty_string() -> None:
    reasoning, reply = P._strip_reasoning("")
    assert reasoning == ""
    assert reply == ""


def test_strip_reasoning_none_like_empty() -> None:
    reasoning, reply = P._strip_reasoning("")
    assert isinstance(reasoning, str)
    assert isinstance(reply, str)


def test_strip_reasoning_multiline_tag() -> None:
    reasoning, _ = P._strip_reasoning("<reasoning>\nline1\nline2\n</reasoning>done")
    assert "line1" in reasoning
    assert "line2" in reasoning


def test_strip_reasoning_returns_tuple() -> None:
    result = P._strip_reasoning("text")
    assert isinstance(result, tuple)
    assert len(result) == 2


# ─── _extract_final_answer ───────────────────────────────────────────────────

def test_extract_final_answer_extracts_tag_content() -> None:
    result = P._extract_final_answer("preamble <answer>42</answer> tail")
    assert result == "42"


def test_extract_final_answer_falls_back_to_full_text() -> None:
    result = P._extract_final_answer("no tag here")
    assert result == "no tag here"


def test_extract_final_answer_empty_string() -> None:
    result = P._extract_final_answer("")
    assert result == ""


def test_extract_final_answer_strips_whitespace() -> None:
    result = P._extract_final_answer("<answer>  spaced  </answer>")
    assert result == "spaced"


def test_extract_final_answer_multiline_answer() -> None:
    result = P._extract_final_answer("<answer>\nline1\nline2\n</answer>")
    assert "line1" in result
    assert "line2" in result


def test_extract_final_answer_returns_string() -> None:
    assert isinstance(P._extract_final_answer("x"), str)


# ─── task_projector_command_parse ────────────────────────────────────────────

def test_command_parse_no_slash_returns_empty_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("hello world"))
    assert result["command"] == ""


def test_command_parse_no_slash_preserves_text() -> None:
    result = asyncio.run(P.task_projector_command_parse("hello world"))
    assert result["argText"] == "hello world"


def test_command_parse_explore_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("/explore some topic"))
    assert result["command"] == "/explore"
    assert result["argText"] == "some topic"


def test_command_parse_consistent_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("/consistent args"))
    assert result["command"] == "/consistent"


def test_command_parse_reflect_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("/reflect lesson"))
    assert result["command"] == "/reflect"


def test_command_parse_image_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("/image a cat"))
    assert result["command"] == "/image"


def test_command_parse_think_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("/think deeply"))
    assert result["command"] == "/think"


def test_command_parse_unknown_slash_returns_empty_command() -> None:
    result = asyncio.run(P.task_projector_command_parse("/unknown stuff"))
    assert result["command"] == ""


def test_command_parse_unknown_slash_preserves_full_text() -> None:
    result = asyncio.run(P.task_projector_command_parse("/unknown stuff"))
    assert "/unknown" in result["argText"]


def test_command_parse_empty_string_returns_empty() -> None:
    result = asyncio.run(P.task_projector_command_parse(""))
    assert result["command"] == ""
    assert result["argText"] == ""


def test_command_parse_returns_dict() -> None:
    result = asyncio.run(P.task_projector_command_parse("text"))
    assert isinstance(result, dict)
    assert "command" in result
    assert "argText" in result


def test_command_parse_no_arg_defaults_empty_text() -> None:
    result = asyncio.run(P.task_projector_command_parse())
    assert isinstance(result, dict)


# ─── task_projector_command_deferred ─────────────────────────────────────────

def test_command_deferred_returns_deferred_true() -> None:
    result = asyncio.run(P.task_projector_command_deferred("/image"))
    assert result["deferred"] is True


def test_command_deferred_has_reply_key() -> None:
    result = asyncio.run(P.task_projector_command_deferred("/image"))
    assert "reply" in result


def test_command_deferred_reply_contains_command() -> None:
    result = asyncio.run(P.task_projector_command_deferred("/think"))
    assert "/think" in result["reply"]


def test_command_deferred_empty_command() -> None:
    result = asyncio.run(P.task_projector_command_deferred(""))
    assert result["deferred"] is True


def test_command_deferred_returns_dict() -> None:
    result = asyncio.run(P.task_projector_command_deferred("x"))
    assert isinstance(result, dict)


# ─── _format_tools_for_prompt ────────────────────────────────────────────────

def test_format_tools_empty_list_returns_none_string() -> None:
    assert P._format_tools_for_prompt([]) == "(none)"


def test_format_tools_single_tool_contains_name() -> None:
    result = P._format_tools_for_prompt([{"name": "search", "description": "Search things"}])
    assert "search" in result


def test_format_tools_single_tool_contains_description() -> None:
    result = P._format_tools_for_prompt([{"name": "x", "description": "Do stuff"}])
    assert "Do stuff" in result


def test_format_tools_multiple_tools_each_on_own_line() -> None:
    result = P._format_tools_for_prompt([
        {"name": "tool_a", "description": "A"},
        {"name": "tool_b", "description": "B"},
    ])
    lines = result.split("\n")
    assert len(lines) == 2


def test_format_tools_contains_args_label() -> None:
    result = P._format_tools_for_prompt([{"name": "x", "description": "y"}])
    assert "ARGS=" in result


def test_format_tools_schema_is_serialized() -> None:
    result = P._format_tools_for_prompt([
        {"name": "x", "description": "y", "schema": {"q": "string"}}
    ])
    assert "q" in result


def test_format_tools_starts_with_dash() -> None:
    result = P._format_tools_for_prompt([{"name": "x", "description": "y"}])
    assert result.startswith("- ")


def test_format_tools_returns_string() -> None:
    assert isinstance(P._format_tools_for_prompt([]), str)


# ─── _parse_tool_calls ───────────────────────────────────────────────────────

def test_parse_tool_calls_no_match_returns_empty() -> None:
    result = P._parse_tool_calls("no tool calls here")
    assert result == []


def test_parse_tool_calls_finds_call() -> None:
    text = '[TOOL_CALL: search({"q": "cats"})]'
    result = P._parse_tool_calls(text)
    assert len(result) == 1


def test_parse_tool_calls_extracts_name() -> None:
    text = '[TOOL_CALL: search({"q": "cats"})]'
    name, _ = P._parse_tool_calls(text)[0]
    assert name == "search"


def test_parse_tool_calls_extracts_args() -> None:
    text = '[TOOL_CALL: search({"q": "cats"})]'
    _, args = P._parse_tool_calls(text)[0]
    assert args.get("q") == "cats"


def test_parse_tool_calls_empty_args() -> None:
    text = "[TOOL_CALL: noop()]"
    result = P._parse_tool_calls(text)
    assert len(result) == 1
    _, args = result[0]
    assert isinstance(args, dict)


def test_parse_tool_calls_invalid_json_args_become_empty_dict() -> None:
    text = "[TOOL_CALL: bad({not valid json})]"
    result = P._parse_tool_calls(text)
    if result:
        _, args = result[0]
        assert isinstance(args, dict)


def test_parse_tool_calls_multiple_calls() -> None:
    text = '[TOOL_CALL: a({"x": 1})] some text [TOOL_CALL: b({"y": 2})]'
    result = P._parse_tool_calls(text)
    assert len(result) == 2


def test_parse_tool_calls_empty_string_returns_empty() -> None:
    assert P._parse_tool_calls("") == []


def test_parse_tool_calls_returns_list() -> None:
    assert isinstance(P._parse_tool_calls("text"), list)


# ─── _guardrail_check ────────────────────────────────────────────────────────

def test_guardrail_clean_text_ok() -> None:
    result = P._guardrail_check("list all actors")
    assert result["ok"] is True


def test_guardrail_rm_rf_blocked() -> None:
    result = P._guardrail_check("please run rm -rf /")
    assert result["ok"] is False


def test_guardrail_drop_table_blocked() -> None:
    result = P._guardrail_check("drop table vertex_actor")
    assert result["ok"] is False


def test_guardrail_shutdown_blocked() -> None:
    result = P._guardrail_check("shutdown -h now")
    assert result["ok"] is False


def test_guardrail_delete_vertex_blocked() -> None:
    result = P._guardrail_check("delete from vertex_actor where 1=1")
    assert result["ok"] is False


def test_guardrail_blocked_has_reason() -> None:
    result = P._guardrail_check("rm -rf /tmp")
    assert "reason" in result
    assert result["reason"]


def test_guardrail_case_insensitive() -> None:
    result = P._guardrail_check("RM -RF /home")
    assert result["ok"] is False


def test_guardrail_empty_string_ok() -> None:
    result = P._guardrail_check("")
    assert result["ok"] is True


def test_guardrail_returns_dict() -> None:
    assert isinstance(P._guardrail_check("safe text"), dict)


# ─── task_projector_reflexion_write — missing required args ──────────────────

def test_reflexion_write_no_convo_id_returns_error() -> None:
    result = asyncio.run(P.task_projector_reflexion_write(lessonText="lesson text"))
    assert result.get("rkey") == ""
    assert "reflexion" in result.get("reply", "")


def test_reflexion_write_no_lesson_returns_error() -> None:
    result = asyncio.run(P.task_projector_reflexion_write(convoId="convo-1"))
    assert result.get("rkey") == ""


def test_reflexion_write_both_empty_returns_error() -> None:
    result = asyncio.run(P.task_projector_reflexion_write())
    assert result.get("rkey") == ""


def test_reflexion_write_returns_dict() -> None:
    result = asyncio.run(P.task_projector_reflexion_write())
    assert isinstance(result, dict)


# ─── task_projector_tools_discover — empty convo returns PM builtin tools ────

def test_tools_discover_no_convo_returns_tools() -> None:
    result = asyncio.run(P.task_projector_tools_discover())
    assert "tools" in result


def test_tools_discover_no_convo_tools_is_list() -> None:
    result = asyncio.run(P.task_projector_tools_discover())
    assert isinstance(result["tools"], list)


def test_tools_discover_no_convo_returns_pm_builtins() -> None:
    result = asyncio.run(P.task_projector_tools_discover())
    assert len(result["tools"]) > 0


def test_tools_discover_returns_dict() -> None:
    result = asyncio.run(P.task_projector_tools_discover())
    assert isinstance(result, dict)


# ─── task_projector_tool_call — missing tool name ────────────────────────────

def test_tool_call_no_name_returns_error() -> None:
    result = asyncio.run(P.task_projector_tool_call())
    assert result["ok"] is False


def test_tool_call_no_name_error_mentions_name() -> None:
    result = asyncio.run(P.task_projector_tool_call())
    assert "name" in result.get("error", "")


def test_tool_call_returns_dict() -> None:
    result = asyncio.run(P.task_projector_tool_call())
    assert isinstance(result, dict)


# ─── task_projector_agent_loop — missing user text ───────────────────────────

def test_agent_loop_no_user_text_returns_early() -> None:
    result = asyncio.run(P.task_projector_agent_loop())
    assert "reply" in result


def test_agent_loop_no_user_text_zero_iterations() -> None:
    result = asyncio.run(P.task_projector_agent_loop())
    assert result.get("iterations") == 0


def test_agent_loop_no_user_text_empty_tools() -> None:
    result = asyncio.run(P.task_projector_agent_loop())
    assert result.get("toolsCalled") == []


def test_agent_loop_returns_dict() -> None:
    result = asyncio.run(P.task_projector_agent_loop())
    assert isinstance(result, dict)


# ─── task_projector_persist_message — missing required args ──────────────────

def test_persist_message_no_convo_id_returns_error() -> None:
    result = asyncio.run(P.task_projector_persist_message(reply="hello"))
    assert result["ok"] is False


def test_persist_message_no_reply_returns_error() -> None:
    result = asyncio.run(P.task_projector_persist_message(convoId="c-1"))
    assert result["ok"] is False


def test_persist_message_no_args_returns_error() -> None:
    result = asyncio.run(P.task_projector_persist_message())
    assert result["ok"] is False


def test_persist_message_error_has_message() -> None:
    result = asyncio.run(P.task_projector_persist_message())
    assert "error" in result


def test_persist_message_returns_dict() -> None:
    result = asyncio.run(P.task_projector_persist_message())
    assert isinstance(result, dict)


# ─── task_projector_tot_expand — stub LLM returns empty, no question ──────────

def test_tot_expand_returns_dict() -> None:
    result = asyncio.run(P.task_projector_tot_expand())
    assert isinstance(result, dict)


def test_tot_expand_has_reply() -> None:
    result = asyncio.run(P.task_projector_tot_expand())
    assert "reply" in result


def test_tot_expand_has_approaches() -> None:
    result = asyncio.run(P.task_projector_tot_expand())
    assert "approaches" in result


def test_tot_expand_approaches_is_list() -> None:
    result = asyncio.run(P.task_projector_tot_expand())
    assert isinstance(result["approaches"], list)


def test_tot_expand_has_scores() -> None:
    result = asyncio.run(P.task_projector_tot_expand())
    assert "scores" in result


def test_tot_expand_has_best_index() -> None:
    result = asyncio.run(P.task_projector_tot_expand())
    assert "bestIndex" in result


# ─── task_projector_sc_parallel — stub LLM returns empty ─────────────────────

def test_sc_parallel_returns_dict() -> None:
    result = asyncio.run(P.task_projector_sc_parallel())
    assert isinstance(result, dict)


def test_sc_parallel_has_reply() -> None:
    result = asyncio.run(P.task_projector_sc_parallel())
    assert "reply" in result


def test_sc_parallel_has_answer() -> None:
    result = asyncio.run(P.task_projector_sc_parallel())
    assert "answer" in result


def test_sc_parallel_has_paths() -> None:
    result = asyncio.run(P.task_projector_sc_parallel())
    assert "paths" in result


def test_sc_parallel_paths_is_list() -> None:
    result = asyncio.run(P.task_projector_sc_parallel())
    assert isinstance(result["paths"], list)


def test_sc_parallel_has_tally() -> None:
    result = asyncio.run(P.task_projector_sc_parallel())
    assert "tally" in result
