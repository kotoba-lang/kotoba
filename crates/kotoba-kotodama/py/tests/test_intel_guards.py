"""Guard and pure-path tests for primitives/intel.py.

intel.py imports kotodama.llm — stub it before loading.
All DB-reaching paths use try/except, so noop cursor is safe.
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

# ── db_sync stub ──────────────────────────────────────────────────────────────
_db_stub = types.ModuleType("kotodama.db_sync")


def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()


_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)

# ── llm stub ──────────────────────────────────────────────────────────────────
_llm_stub = types.ModuleType("kotodama.llm")
_llm_stub.call_tier = lambda *a, **kw: {"content": "", "model": "", "usage": {}}  # type: ignore[attr-defined]
_llm_stub.call_tier_json = lambda *a, **kw: {"ok": False, "error": "stub"}  # type: ignore[attr-defined]
_llm_stub.LlmError = type("LlmError", (Exception,), {})  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.llm", _llm_stub)

# ── kotodama package stub ───────────────────────────────────────────────────
if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

# ensure kotodama.llm is accessible as attribute of kotodama
_pyma = sys.modules["kotodama"]
if not hasattr(_pyma, "llm"):
    _pyma.llm = _llm_stub  # type: ignore[attr-defined]

# ── load intel ────────────────────────────────────────────────────────────────
_MOD_NAME = "_intel_guards"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "intel.py"
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db

I = sys.modules[_MOD_NAME]


# ─── task_intel_run_create — dryRun=True is pure ─────────────────────────────

def test_run_create_dry_run_returns_dict() -> None:
    result = asyncio.run(I.task_intel_run_create(dryRun=True))
    assert isinstance(result, dict)


def test_run_create_dry_run_flag_set() -> None:
    result = asyncio.run(I.task_intel_run_create(dryRun=True))
    assert result["dryRun"] is True


def test_run_create_dry_run_has_run_id() -> None:
    result = asyncio.run(I.task_intel_run_create(dryRun=True))
    assert result["runId"]


def test_run_create_dry_run_status_running() -> None:
    result = asyncio.run(I.task_intel_run_create(dryRun=True))
    assert result["status"] == "running"


# ─── task_intel_owl_validate — pure validation ───────────────────────────────

def test_owl_validate_empty_candidates_returns_empty() -> None:
    result = asyncio.run(I.task_intel_owl_validate())
    assert result["validCount"] == 0
    assert result["invalidCount"] == 0


def test_owl_validate_invalid_kind_counts_invalid() -> None:
    result = asyncio.run(I.task_intel_owl_validate(
        candidates=[{"subjectKind": "invalid_kind", "vertexId": "v1"}]
    ))
    assert result["invalidCount"] == 1
    assert result["validCount"] == 0


def test_owl_validate_valid_candidate_passes() -> None:
    result = asyncio.run(I.task_intel_owl_validate(
        candidates=[{"subjectKind": "organization", "vertexId": "v1"}]
    ))
    assert result["validCount"] == 1


def test_owl_validate_missing_vertex_id_invalid() -> None:
    result = asyncio.run(I.task_intel_owl_validate(
        candidates=[{"subjectKind": "organization", "vertexId": ""}]
    ))
    assert result["invalidCount"] == 1


def test_owl_validate_returns_dict() -> None:
    result = asyncio.run(I.task_intel_owl_validate())
    assert isinstance(result, dict)


# ─── task_intel_langgraph_resolve — empty candidates early-return ─────────────

def test_langgraph_resolve_empty_candidates_early_return() -> None:
    result = asyncio.run(I.task_intel_langgraph_resolve(validCandidates=[]))
    assert result["resolvedEdges"] == []


def test_langgraph_resolve_no_candidates_returns_dict() -> None:
    result = asyncio.run(I.task_intel_langgraph_resolve())
    assert isinstance(result, dict)


def test_langgraph_resolve_stub_llm_returns_empty_edges() -> None:
    # stub call_tier_json returns {"ok": False, "error": "stub"} — not a list/dict with edges
    cands = [{"subjectKind": "organization", "vertexId": "v1", "label": "Org1"}]
    result = asyncio.run(I.task_intel_langgraph_resolve(validCandidates=cands))
    assert "resolvedEdges" in result


# ─── task_intel_edge_materialize — empty/dryRun paths ────────────────────────

def test_edge_materialize_empty_edges_zero_counts() -> None:
    result = asyncio.run(I.task_intel_edge_materialize(resolvedEdges=[]))
    assert result["candidateCount"] == 0
    assert result["activeCount"] == 0


def test_edge_materialize_dry_run_no_db() -> None:
    edge = {"srcVertexId": "v1", "dstVertexId": "v2", "predicate": "OWNS", "confidence": 0.9}
    result = asyncio.run(I.task_intel_edge_materialize(resolvedEdges=[edge], dryRun=True))
    assert result["activeCount"] == 1


def test_edge_materialize_returns_dict() -> None:
    result = asyncio.run(I.task_intel_edge_materialize())
    assert isinstance(result, dict)


# ─── task_intel_entity_resolve — empty query early-return ─────────────────────

def test_entity_resolve_empty_query_returns_empty() -> None:
    result = asyncio.run(I.task_intel_entity_resolve(query=""))
    assert result["candidates"] == []
    assert result["count"] == 0


def test_entity_resolve_empty_query_returns_dict() -> None:
    result = asyncio.run(I.task_intel_entity_resolve())
    assert isinstance(result, dict)


# ─── task_intel_candidate_scan — noop cursor returns empty ───────────────────

def test_candidate_scan_noop_cursor_empty_candidates() -> None:
    result = asyncio.run(I.task_intel_candidate_scan())
    assert result["candidates"] == []


def test_candidate_scan_returns_dict() -> None:
    result = asyncio.run(I.task_intel_candidate_scan())
    assert isinstance(result, dict)


def test_candidate_scan_has_count() -> None:
    result = asyncio.run(I.task_intel_candidate_scan())
    assert "count" in result


# ─── task_intel_dependency_list — noop cursor returns empty ──────────────────

def test_dependency_list_noop_cursor_empty_edges() -> None:
    result = asyncio.run(I.task_intel_dependency_list())
    assert result["edges"] == []


def test_dependency_list_returns_dict() -> None:
    result = asyncio.run(I.task_intel_dependency_list())
    assert isinstance(result, dict)


def test_dependency_list_has_count() -> None:
    result = asyncio.run(I.task_intel_dependency_list())
    assert "count" in result
