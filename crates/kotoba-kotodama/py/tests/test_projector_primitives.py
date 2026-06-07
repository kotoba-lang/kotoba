"""Tests for projector primitives (BPMN/LangGraph project-manager agent)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest  # noqa: E402
from kotodama.primitives import projector as PR  # noqa: E402


@pytest.fixture()
def _stub_db():
    with patch("kotodama.primitives.projector.sync_cursor") as m:
        cur = MagicMock()
        cur.description = [("lesson",), ("attempt",), ("outcome",), ("created_at",)]
        cur.fetchall.return_value = []
        cur.fetchone.return_value = None
        cur.rowcount = 1
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


# ─── _strip_reasoning (pure) ─────────────────────────────────────────────────

def test_strip_reasoning_extracts_tag():
    text = "<reasoning>some analysis</reasoning>Final answer here"
    reasoning, cleaned = PR._strip_reasoning(text)
    assert reasoning == "some analysis"
    assert "reasoning" not in cleaned
    assert "Final answer here" in cleaned


def test_strip_reasoning_no_tag_returns_empty_reasoning():
    reasoning, cleaned = PR._strip_reasoning("Just a plain reply")
    assert reasoning == ""
    assert cleaned == "Just a plain reply"


def test_strip_reasoning_empty_string():
    reasoning, cleaned = PR._strip_reasoning("")
    assert reasoning == ""
    assert cleaned == ""


# ─── _extract_final_answer (pure) ────────────────────────────────────────────

def test_extract_final_answer_extracts_tag():
    text = "<reasoning>think</reasoning><answer>The final answer</answer>"
    result = PR._extract_final_answer(text)
    assert result == "The final answer"


def test_extract_final_answer_no_tag_returns_full_text():
    result = PR._extract_final_answer("No answer tags here")
    assert result == "No answer tags here"


def test_extract_final_answer_empty():
    assert PR._extract_final_answer("") == ""


# ─── _guardrail_check (pure) ─────────────────────────────────────────────────

def test_guardrail_check_ok_on_clean_text():
    result = PR._guardrail_check("Please find all open tasks for this project")
    assert result["ok"] is True


def test_guardrail_check_blocks_rm_rf():
    result = PR._guardrail_check("rm -rf /")
    assert result["ok"] is False
    assert "policy_block" in result.get("reason", "")


def test_guardrail_check_blocks_drop_table():
    result = PR._guardrail_check("DROP TABLE vertex_actor")
    assert result["ok"] is False


def test_guardrail_check_blocks_delete_from_vertex():
    result = PR._guardrail_check("delete from vertex_repo_record")
    assert result["ok"] is False


# ─── _format_tools_for_prompt (pure) ─────────────────────────────────────────

def test_format_tools_empty_list():
    result = PR._format_tools_for_prompt([])
    assert result == "(none)"


def test_format_tools_renders_tool_entry():
    tools = [{"name": "pm.graph_search", "description": "Search the graph", "schema": {}}]
    result = PR._format_tools_for_prompt(tools)
    assert "pm.graph_search" in result
    assert "Search the graph" in result


# ─── _parse_tool_calls (pure) ────────────────────────────────────────────────

def test_parse_tool_calls_finds_call():
    text = 'Some text [TOOL_CALL: pm.graph_search({"query": "hello"})] more text'
    calls = PR._parse_tool_calls(text)
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "pm.graph_search"
    assert args["query"] == "hello"


def test_parse_tool_calls_empty_text():
    assert PR._parse_tool_calls("") == []


def test_parse_tool_calls_no_calls():
    assert PR._parse_tool_calls("Plain text with no tool calls") == []


def test_parse_tool_calls_invalid_json_returns_empty_dict():
    # Regex requires args to start with '{'; invalid JSON inside braces → {}
    text = '[TOOL_CALL: pm.graph_search({invalid json here})]'
    calls = PR._parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0][1] == {}


# ─── task_projector_command_parse (async) ────────────────────────────────────

def test_command_parse_no_slash_returns_empty_command():
    result = asyncio.run(PR.task_projector_command_parse(text="hello world"))
    assert result["command"] == ""
    assert result["argText"] == "hello world"


def test_command_parse_known_command_extracted():
    result = asyncio.run(PR.task_projector_command_parse(text="/explore some topic"))
    assert result["command"] == "/explore"
    assert result["argText"] == "some topic"


def test_command_parse_unknown_command_returns_empty():
    result = asyncio.run(PR.task_projector_command_parse(text="/unknowncmd arg"))
    assert result["command"] == ""


def test_command_parse_empty_text():
    result = asyncio.run(PR.task_projector_command_parse(text=""))
    assert result["command"] == ""


def test_command_parse_all_known_commands():
    for cmd in ("/explore", "/consistent", "/reflect", "/image", "/think"):
        result = asyncio.run(PR.task_projector_command_parse(text=f"{cmd} arg"))
        assert result["command"] == cmd


# ─── task_projector_command_deferred (async) ─────────────────────────────────

def test_command_deferred_returns_deferred_true():
    result = asyncio.run(PR.task_projector_command_deferred(command="/image"))
    assert result["deferred"] is True
    assert "/image" in result["reply"]


# ─── task_projector_reflexion_load (async, table absent → empty) ─────────────

def test_reflexion_load_no_convo_id_returns_empty():
    result = asyncio.run(PR.task_projector_reflexion_load(convoId=""))
    assert result["memories"] == []


def test_reflexion_load_table_absent_returns_empty(_stub_db):
    _stub_db.fetchone.return_value = None
    result = asyncio.run(PR.task_projector_reflexion_load(convoId="convo-001"))
    assert result["memories"] == []


# ─── task_projector_tool_call (async) ────────────────────────────────────────

def test_tool_call_no_name_returns_error():
    result = asyncio.run(PR.task_projector_tool_call(name=""))
    assert result["ok"] is False
    assert "tool name required" in result["error"]


def test_tool_call_graph_search_empty_query(_stub_db):
    result = asyncio.run(PR.task_projector_tool_call(
        name="pm.graph_search", args={"query": ""}, convoId="c1"
    ))
    assert result["ok"] is True
    assert result["result"].get("note") == "empty query"


def test_tool_call_search_agents_empty_query(_stub_db):
    result = asyncio.run(PR.task_projector_tool_call(
        name="pm.search_agents", args={"query": ""}, convoId="c1"
    ))
    assert result["ok"] is True
    assert result["result"].get("agents") == []


# ─── task_projector_agent_loop (async, no userText) ──────────────────────────

def test_agent_loop_empty_user_text_returns_default():
    result = asyncio.run(PR.task_projector_agent_loop(
        convoId="c1", userText="",
    ))
    assert "reply" in result
    assert result["iterations"] == 0


# ─── task_projector_persist_message (async) ──────────────────────────────────

def test_persist_message_no_convo_id_returns_error():
    result = asyncio.run(PR.task_projector_persist_message(
        convoId="", reply="some reply"
    ))
    assert result["ok"] is False


def test_persist_message_no_reply_returns_error():
    result = asyncio.run(PR.task_projector_persist_message(
        convoId="convo-001", reply=""
    ))
    assert result["ok"] is False


def test_persist_message_direct_insert(_stub_db):
    import os
    with patch.dict(os.environ, {"PROJECTOR_PERSIST_VIA_PDS": "0"}):
        result = asyncio.run(PR.task_projector_persist_message(
            convoId="convo-001",
            callerDid="did:web:user.etzhayyim.com",
            reply="Project is on track",
        ))
    assert result["ok"] is True
    assert result["uri"].startswith("at://")


# ─── task_projector_auth_mint (async) ────────────────────────────────────────

def test_auth_mint_no_lxm_returns_error():
    result = asyncio.run(PR.task_projector_auth_mint(lxm=""))
    assert result["ok"] is False
    assert "lxm required" in result["error"]


# ─── register ────────────────────────────────────────────────────────────────

def test_register_exposes_eleven_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    PR.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "projector.command.parse",
        "projector.command.deferred",
        "projector.reflexion.load",
        "projector.reflexion.write",
        "projector.tools.discover",
        "projector.tool.call",
        "projector.agent.loop",
        "projector.tot.expand",
        "projector.sc.parallel",
        "projector.persist.message",
        "projector.auth.mint",
    }


# ─── _agent_route ─────────────────────────────────────────────────────────────

def test_agent_route_done_returns_end():
    state = {"done": True, "iterations": 0, "maxIterations": 6}
    assert PR._agent_route(state) == "end"


def test_agent_route_pending_tool_returns_guardrail():
    state = {"__pending_tool": {"name": "my_tool"}, "iterations": 0, "maxIterations": 6}
    assert PR._agent_route(state) == "guardrail"


def test_agent_route_max_iterations_returns_end():
    state = {"done": False, "iterations": 6, "maxIterations": 6}
    assert PR._agent_route(state) == "end"


def test_agent_route_normal_returns_reason():
    state = {"done": False, "iterations": 2, "maxIterations": 6}
    assert PR._agent_route(state) == "reason"


def test_agent_route_empty_state_returns_reason():
    assert PR._agent_route({}) == "reason"


def test_agent_route_done_takes_priority_over_pending_tool():
    state = {"done": True, "__pending_tool": {"name": "t"}, "iterations": 0, "maxIterations": 6}
    assert PR._agent_route(state) == "end"


def test_agent_route_iterations_equals_max_returns_end():
    state = {"iterations": 3, "maxIterations": 3}
    assert PR._agent_route(state) == "end"


def test_agent_route_iterations_below_max_returns_reason():
    state = {"iterations": 2, "maxIterations": 10}
    assert PR._agent_route(state) == "reason"


# ─── _build_system_prompt ─────────────────────────────────────────────────────

def test_build_system_prompt_returns_string():
    result = PR._build_system_prompt({})
    assert isinstance(result, str) and len(result) > 0


def test_build_system_prompt_contains_project_manager():
    result = PR._build_system_prompt({})
    assert "project-manager" in result.lower()


def test_build_system_prompt_contains_tool_call_syntax():
    result = PR._build_system_prompt({})
    assert "TOOL_CALL" in result


def test_build_system_prompt_contains_answer_tag():
    result = PR._build_system_prompt({})
    assert "<answer>" in result


def test_build_system_prompt_includes_reflexion_memory():
    state = {"reflexionMemory": [{"lesson": "Always validate inputs first"}]}
    result = PR._build_system_prompt(state)
    assert "Always validate inputs first" in result


def test_build_system_prompt_limits_memory_to_last_5():
    lessons = [{"lesson": f"lesson-{i}"} for i in range(10)]
    state = {"reflexionMemory": lessons}
    result = PR._build_system_prompt(state)
    # Only last 5 lessons should appear
    assert "lesson-9" in result
    assert "lesson-4" not in result  # earlier lessons trimmed


def test_build_system_prompt_no_memory_section_when_empty():
    result = PR._build_system_prompt({"reflexionMemory": []})
    assert "Past lessons" not in result


def test_build_system_prompt_includes_available_tools_section():
    result = PR._build_system_prompt({})
    assert "Available tools" in result
