"""Tests for pure helpers in registry.py and handlers/user_task_sink.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import importlib.util

from kotodama import registry

# Load user_task_sink directly (bypass kotodama.handlers __init__ which
# registers all @udf handlers as a side effect and conflicts when tests run
# alongside test_handler_pure_functions.py that loads bpmn etc. via _load).
_uts_path = _py_src / "kotodama" / "handlers" / "user_task_sink.py"
_uts_spec = importlib.util.spec_from_file_location("_uts_direct", str(_uts_path))
_uts_mod = importlib.util.module_from_spec(_uts_spec)  # type: ignore[arg-type]
sys.modules["_uts_direct"] = _uts_mod  # needed so @dataclass can resolve its module
_uts_spec.loader.exec_module(_uts_mod)  # type: ignore[union-attr]
_parse_maybe_json = _uts_mod._parse_maybe_json


# ─── registry.HandlerEntry ───────────────────────────────────────────────

def test_handler_entry_stores_nsid() -> None:
    def dummy() -> None:
        pass
    entry = registry.HandlerEntry(
        nsid="ai.test.x",
        fn=dummy,
        io_threads=10,
        capability_tags=("tag1",),
        agent_tool="my tool",
    )
    assert entry.nsid == "ai.test.x"


def test_handler_entry_stores_fn() -> None:
    def my_fn() -> None:
        pass
    entry = registry.HandlerEntry(
        nsid="ai.test.y",
        fn=my_fn,
        io_threads=100,
        capability_tags=(),
        agent_tool=None,
    )
    assert entry.fn is my_fn


def test_handler_entry_stores_io_threads() -> None:
    def f() -> None:
        pass
    entry = registry.HandlerEntry(
        nsid="ai.test.z",
        fn=f,
        io_threads=50,
        capability_tags=(),
        agent_tool=None,
    )
    assert entry.io_threads == 50


def test_handler_entry_capability_tags() -> None:
    def f() -> None:
        pass
    entry = registry.HandlerEntry(
        nsid="ai.test.w",
        fn=f,
        io_threads=100,
        capability_tags=("nlp", "classify"),
        agent_tool=None,
    )
    assert entry.capability_tags == ("nlp", "classify")


def test_handler_entry_agent_tool_none() -> None:
    def f() -> None:
        pass
    entry = registry.HandlerEntry(
        nsid="ai.test.v",
        fn=f,
        io_threads=100,
        capability_tags=(),
        agent_tool=None,
    )
    assert entry.agent_tool is None


def test_handler_entry_is_frozen() -> None:
    def f() -> None:
        pass
    entry = registry.HandlerEntry(
        nsid="ai.test.u",
        fn=f,
        io_threads=100,
        capability_tags=(),
        agent_tool=None,
    )
    try:
        entry.nsid = "modified"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass


# ─── registry.registered ─────────────────────────────────────────────────

def test_registered_returns_dict() -> None:
    result = registry.registered()
    assert isinstance(result, dict)


def test_registered_snapshot_is_copy() -> None:
    snapshot1 = registry.registered()
    snapshot2 = registry.registered()
    assert snapshot1 == snapshot2


# ─── registry.agent_tools ────────────────────────────────────────────────

def test_agent_tools_returns_list() -> None:
    result = registry.agent_tools()
    assert isinstance(result, list)


def test_agent_tools_entries_have_name() -> None:
    for tool in registry.agent_tools():
        assert "name" in tool


def test_agent_tools_entries_have_description() -> None:
    for tool in registry.agent_tools():
        assert "description" in tool


def test_agent_tools_entries_have_parameters() -> None:
    for tool in registry.agent_tools():
        assert "parameters" in tool
        assert isinstance(tool["parameters"], list)


def test_agent_tools_capability_tags_is_list() -> None:
    for tool in registry.agent_tools():
        assert isinstance(tool["capability_tags"], list)


# ─── _parse_maybe_json ───────────────────────────────────────────────────

def test_parse_maybe_json_none_returns_none() -> None:
    assert _parse_maybe_json(None) is None


def test_parse_maybe_json_list_passthrough() -> None:
    val = [1, 2, 3]
    assert _parse_maybe_json(val) is val


def test_parse_maybe_json_dict_passthrough() -> None:
    val = {"a": 1}
    assert _parse_maybe_json(val) is val


def test_parse_maybe_json_json_string_array() -> None:
    result = _parse_maybe_json('["group1", "group2"]')
    assert result == ["group1", "group2"]


def test_parse_maybe_json_json_string_object() -> None:
    result = _parse_maybe_json('{"key": "val"}')
    assert result == {"key": "val"}


def test_parse_maybe_json_plain_string_passthrough() -> None:
    result = _parse_maybe_json("hello world")
    assert result == "hello world"


def test_parse_maybe_json_bare_string_does_not_parse() -> None:
    result = _parse_maybe_json("not json at all")
    assert result == "not json at all"


def test_parse_maybe_json_invalid_json_array_prefix_returns_string() -> None:
    result = _parse_maybe_json("[not valid json")
    assert isinstance(result, str)


def test_parse_maybe_json_empty_string_passthrough() -> None:
    result = _parse_maybe_json("")
    assert result == ""


def test_parse_maybe_json_integer_passthrough() -> None:
    result = _parse_maybe_json(42)
    assert result == 42


# ─── _parse_activated ────────────────────────────────────────────────────────

import json as _json
from unittest.mock import MagicMock as _MagicMock

_parse_activated = _uts_mod._parse_activated
_ActivatedUserTask = _uts_mod.ActivatedUserTask


def _make_job(**kwargs) -> _MagicMock:
    job = _MagicMock()
    job.key = kwargs.get("key", 1001)
    job.processInstanceKey = kwargs.get("processInstanceKey", 2001)
    job.processDefinitionKey = kwargs.get("processDefinitionKey", 3001)
    job.bpmnProcessId = kwargs.get("bpmnProcessId", "my-process")
    job.elementId = kwargs.get("elementId", "UserTask_1")
    job.customHeaders = kwargs.get("customHeaders", "")
    job.variables = kwargs.get("variables", "")
    return job


def test_parse_activated_returns_dataclass() -> None:
    job = _make_job()
    result = _parse_activated(job)
    assert isinstance(result, _ActivatedUserTask)


def test_parse_activated_job_key_parsed() -> None:
    job = _make_job(key=9999)
    result = _parse_activated(job)
    assert result.job_key == 9999


def test_parse_activated_bpmn_process_id() -> None:
    job = _make_job(bpmnProcessId="order-process")
    result = _parse_activated(job)
    assert result.bpmn_process_id == "order-process"


def test_parse_activated_element_id() -> None:
    job = _make_job(elementId="ReviewTask")
    result = _parse_activated(job)
    assert result.element_id == "ReviewTask"


def test_parse_activated_variables_parsed() -> None:
    job = _make_job(variables=_json.dumps({"orderId": "ORD-001", "amount": 500}))
    result = _parse_activated(job)
    assert result.variables["orderId"] == "ORD-001"
    assert result.variables["amount"] == 500


def test_parse_activated_empty_variables_returns_empty_dict() -> None:
    job = _make_job(variables="")
    result = _parse_activated(job)
    assert result.variables == {}


def test_parse_activated_invalid_variables_returns_empty_dict() -> None:
    job = _make_job(variables="not valid json")
    result = _parse_activated(job)
    assert result.variables == {}


def test_parse_activated_candidate_groups_from_json_array() -> None:
    headers = _json.dumps({"io.camunda.zeebe:candidateGroups": '["group-a", "group-b"]'})
    job = _make_job(customHeaders=headers)
    result = _parse_activated(job)
    assert "group-a" in result.candidate_groups


def test_parse_activated_empty_headers_returns_empty_groups() -> None:
    job = _make_job(customHeaders="")
    result = _parse_activated(job)
    assert result.candidate_groups == []
    assert result.candidate_users == []
