"""Tests for pure helpers in handlers/user_task_sink.py.

_parse_maybe_json and _parse_activated are pure computation:
no DB, no gRPC, no asyncio. They transform Zeebe job payload dicts
into typed Python values.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub grpc and zeebe_grpc so the module-level try/except resolves to None
_grpc_stub = types.ModuleType("grpc")
_grpc_aio_stub = types.ModuleType("grpc.aio")
_grpc_stub.aio = _grpc_aio_stub  # type: ignore[attr-defined]
sys.modules.setdefault("grpc", _grpc_stub)
sys.modules.setdefault("grpc.aio", _grpc_aio_stub)

_zeebe_grpc_stub = types.ModuleType("zeebe_grpc")
_zeebe_pb2_stub = types.ModuleType("zeebe_grpc.gateway_pb2")
_zeebe_pb2_grpc_stub = types.ModuleType("zeebe_grpc.gateway_pb2_grpc")
sys.modules.setdefault("zeebe_grpc", _zeebe_grpc_stub)
sys.modules.setdefault("zeebe_grpc.gateway_pb2", _zeebe_pb2_stub)
sys.modules.setdefault("zeebe_grpc.gateway_pb2_grpc", _zeebe_pb2_grpc_stub)

# Stub kotodama.db_sync
_db_stub = types.ModuleType("kotodama.db_sync")
_db_stub.execute = lambda *a, **kw: None  # type: ignore[attr-defined]
_db_stub.fetch_one = lambda *a, **kw: None  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)
sys.modules.setdefault("kotodama", types.ModuleType("kotodama"))

_MOD_NAME = "_user_task_sink_pure"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "handlers" / "user_task_sink.py"
    _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

M = sys.modules[_MOD_NAME]


# ─── _parse_maybe_json ───────────────────────────────────────────────────────

def test_parse_maybe_json_none_returns_none() -> None:
    assert M._parse_maybe_json(None) is None


def test_parse_maybe_json_list_returns_list() -> None:
    lst = ["a", "b"]
    assert M._parse_maybe_json(lst) == lst


def test_parse_maybe_json_dict_returns_dict() -> None:
    d = {"x": 1}
    assert M._parse_maybe_json(d) == d


def test_parse_maybe_json_json_array_string_parsed() -> None:
    result = M._parse_maybe_json('["reviewers","editors"]')
    assert result == ["reviewers", "editors"]


def test_parse_maybe_json_json_object_string_parsed() -> None:
    result = M._parse_maybe_json('{"key": "val"}')
    assert result == {"key": "val"}


def test_parse_maybe_json_plain_string_returned_as_is() -> None:
    assert M._parse_maybe_json("plain") == "plain"


def test_parse_maybe_json_invalid_json_string_returned_as_is() -> None:
    result = M._parse_maybe_json("[not valid json")
    assert result == "[not valid json"


def test_parse_maybe_json_integer_returned_as_is() -> None:
    assert M._parse_maybe_json(42) == 42


def test_parse_maybe_json_empty_string_returned_as_is() -> None:
    assert M._parse_maybe_json("") == ""


# ─── _parse_activated ────────────────────────────────────────────────────────

class _FakeJob:
    """Minimal stub matching the zeebe_grpc ActivatedJob attributes."""
    def __init__(
        self,
        key: int = 12345,
        processInstanceKey: int = 1,
        processDefinitionKey: int = 2,
        bpmnProcessId: str = "my-process",
        elementId: str = "Task_1",
        customHeaders: str = "",
        variables: str = "",
    ):
        self.key = key
        self.processInstanceKey = processInstanceKey
        self.processDefinitionKey = processDefinitionKey
        self.bpmnProcessId = bpmnProcessId
        self.elementId = elementId
        self.customHeaders = customHeaders
        self.variables = variables


def _make_headers(**kw: str) -> str:
    return json.dumps(kw)


def test_parse_activated_returns_dataclass() -> None:
    task = M._parse_activated(_FakeJob())
    assert isinstance(task, M.ActivatedUserTask)


def test_parse_activated_job_key() -> None:
    task = M._parse_activated(_FakeJob(key=99))
    assert task.job_key == 99


def test_parse_activated_process_instance_key() -> None:
    task = M._parse_activated(_FakeJob(processInstanceKey=42))
    assert task.process_instance_key == 42


def test_parse_activated_bpmn_process_id() -> None:
    task = M._parse_activated(_FakeJob(bpmnProcessId="approve-leave"))
    assert task.bpmn_process_id == "approve-leave"


def test_parse_activated_element_id() -> None:
    task = M._parse_activated(_FakeJob(elementId="Task_Review"))
    assert task.element_id == "Task_Review"


def test_parse_activated_candidate_groups_from_header() -> None:
    headers = _make_headers(**{M.HDR_CANDIDATE_GROUPS: '["managers","leads"]'})
    task = M._parse_activated(_FakeJob(customHeaders=headers))
    assert "managers" in task.candidate_groups
    assert "leads" in task.candidate_groups


def test_parse_activated_candidate_users_from_header() -> None:
    headers = _make_headers(**{M.HDR_CANDIDATE_USERS: '["alice","bob"]'})
    task = M._parse_activated(_FakeJob(customHeaders=headers))
    assert "alice" in task.candidate_users


def test_parse_activated_assignee_from_header() -> None:
    headers = _make_headers(**{M.HDR_ASSIGNEE: "charlie"})
    task = M._parse_activated(_FakeJob(customHeaders=headers))
    assert task.assignee == "charlie"


def test_parse_activated_form_key_from_header() -> None:
    headers = _make_headers(**{M.HDR_FORM_KEY: "form:approval:v1"})
    task = M._parse_activated(_FakeJob(customHeaders=headers))
    assert task.form_key == "form:approval:v1"


def test_parse_activated_due_date_from_header() -> None:
    headers = _make_headers(**{M.HDR_DUE_DATE: "2026-05-01T00:00:00Z"})
    task = M._parse_activated(_FakeJob(customHeaders=headers))
    assert task.due_date == "2026-05-01T00:00:00Z"


def test_parse_activated_element_name_from_header() -> None:
    headers = _make_headers(**{M.HDR_USER_TASK_NAME: "Review Application"})
    task = M._parse_activated(_FakeJob(customHeaders=headers))
    assert task.element_name == "Review Application"


def test_parse_activated_variables_parsed() -> None:
    vars_json = json.dumps({"applicant": "alice", "dept": "hr"})
    task = M._parse_activated(_FakeJob(variables=vars_json))
    assert task.variables["applicant"] == "alice"


def test_parse_activated_empty_candidate_groups_is_list() -> None:
    task = M._parse_activated(_FakeJob())
    assert isinstance(task.candidate_groups, list)


def test_parse_activated_empty_candidate_users_is_list() -> None:
    task = M._parse_activated(_FakeJob())
    assert isinstance(task.candidate_users, list)


def test_parse_activated_no_assignee_is_none() -> None:
    task = M._parse_activated(_FakeJob())
    assert task.assignee is None


def test_parse_activated_no_form_key_is_none() -> None:
    task = M._parse_activated(_FakeJob())
    assert task.form_key is None


def test_parse_activated_invalid_headers_json_gives_empty() -> None:
    task = M._parse_activated(_FakeJob(customHeaders="not json"))
    assert task.candidate_groups == []


def test_parse_activated_invalid_variables_json_gives_empty_dict() -> None:
    task = M._parse_activated(_FakeJob(variables="not json"))
    assert task.variables == {}
