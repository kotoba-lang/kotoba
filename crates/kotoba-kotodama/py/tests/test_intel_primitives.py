"""Tests for intel primitives (pure helpers + mocked DB/LLM tasks)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import intel as IN  # noqa: E402


# ─── pure helper tests ────────────────────────────────────────────────────

def test_run_vid_format():
    vid = IN._run_vid("abc123")
    assert vid.startswith("at://did:web:intel.etzhayyim.com/")
    assert "abc123" in vid


def test_edge_id_is_deterministic():
    a = IN._edge_id("src:1", "dst:2", "OWNS")
    b = IN._edge_id("src:1", "dst:2", "OWNS")
    assert a == b
    assert len(a) > 10


def test_edge_id_differs_for_different_inputs():
    a = IN._edge_id("src:1", "dst:2", "OWNS")
    b = IN._edge_id("src:1", "dst:2", "CONTROLS")
    assert a != b


def test_utc_now_returns_iso_string():
    now = IN._utc_now()
    assert "T" in now
    assert now.endswith("Z")


# ─── task_intel_run_create (dryRun) ──────────────────────────────────────

def test_run_create_dry_run_returns_running():
    out = asyncio.run(IN.task_intel_run_create(dryRun=True))
    assert out["status"] == "running"
    assert out["dryRun"] is True
    assert "runId" in out
    assert out["vertexId"].startswith("at://")


def test_run_create_with_scope():
    out = asyncio.run(IN.task_intel_run_create(
        scope={"subjectKind": "company", "lei": "ABC123"},
        triggerKind="manual",
        dryRun=True,
    ))
    assert out["status"] == "running"


# ─── task_intel_owl_validate (pure logic) ────────────────────────────────

def test_owl_validate_accepts_valid_candidates():
    cands = [
        {"vertexId": "at://v1", "subjectKind": "organization"},
        {"vertexId": "at://v2", "subjectKind": "company"},
    ]
    out = asyncio.run(IN.task_intel_owl_validate(candidates=cands, runId="run1"))
    assert out["validCount"] == 2
    assert out["invalidCount"] == 0


def test_owl_validate_rejects_unknown_kind():
    cands = [{"vertexId": "at://v1", "subjectKind": "spaceship"}]
    out = asyncio.run(IN.task_intel_owl_validate(candidates=cands))
    assert out["validCount"] == 0
    assert out["invalidCount"] == 1


def test_owl_validate_rejects_non_dict():
    out = asyncio.run(IN.task_intel_owl_validate(candidates=["not-a-dict", 42]))
    assert out["invalidCount"] == 2


def test_owl_validate_rejects_missing_vertex_id():
    cands = [{"subjectKind": "company"}]  # no vertexId
    out = asyncio.run(IN.task_intel_owl_validate(candidates=cands))
    assert out["invalidCount"] == 1


def test_owl_validate_empty_candidates():
    out = asyncio.run(IN.task_intel_owl_validate(candidates=[]))
    assert out["validCount"] == 0
    assert out["invalidCount"] == 0


def test_owl_validate_all_known_subject_kinds():
    for kind in IN._VALID_SUBJECT_KINDS:
        out = asyncio.run(IN.task_intel_owl_validate(
            candidates=[{"vertexId": "at://v", "subjectKind": kind}]
        ))
        assert out["validCount"] == 1, f"Expected kind {kind!r} to be valid"


# ─── task_intel_edge_materialize (dryRun) ────────────────────────────────

def test_edge_materialize_dry_run_high_confidence():
    edges = [
        {"srcVertexId": "at://v1", "dstVertexId": "at://v2",
         "predicate": "OWNS", "confidence": 0.9, "evidenceSummary": "Direct ownership"},
    ]
    out = asyncio.run(IN.task_intel_edge_materialize(
        runId="run1", resolvedEdges=edges, dryRun=True,
    ))
    assert out["activeCount"] == 1
    assert out["reviewCount"] == 0
    assert out["candidateCount"] == 1


def test_edge_materialize_dry_run_low_confidence_goes_to_review():
    edges = [
        {"srcVertexId": "at://v1", "dstVertexId": "at://v2",
         "predicate": "CONTROLS", "confidence": 0.6},
    ]
    out = asyncio.run(IN.task_intel_edge_materialize(resolvedEdges=edges, dryRun=True))
    assert out["reviewCount"] == 1
    assert out["activeCount"] == 0


def test_edge_materialize_skips_invalid_edges():
    edges = [
        "not-a-dict",
        {"srcVertexId": "", "dstVertexId": "at://v2", "predicate": "OWNS"},  # empty src
        {"srcVertexId": "at://v1", "dstVertexId": "at://v2", "predicate": ""},  # empty predicate
    ]
    out = asyncio.run(IN.task_intel_edge_materialize(resolvedEdges=edges, dryRun=True))
    assert out["candidateCount"] == 0


def test_edge_materialize_empty_edges():
    out = asyncio.run(IN.task_intel_edge_materialize(resolvedEdges=[], dryRun=True))
    assert out["candidateCount"] == 0


# ─── task_intel_langgraph_resolve (mocked LLM) ───────────────────────────

def test_langgraph_resolve_empty_candidates():
    out = asyncio.run(IN.task_intel_langgraph_resolve(runId="r1", validCandidates=[]))
    assert out["resolvedEdges"] == []


def test_langgraph_resolve_with_mocked_llm(monkeypatch):
    # Patch via IN._llm to reach the exact module reference intel.py holds
    monkeypatch.setattr(IN._llm, "call_tier_json", lambda **kw: [
        {"srcVertexId": "at://v1", "dstVertexId": "at://v2",
         "predicate": "OWNS", "confidence": 0.85, "evidenceSummary": "Direct control"}
    ])
    cands = [{"vertexId": "at://v1", "label": "Corp A", "subjectKind": "company"}]
    out = asyncio.run(IN.task_intel_langgraph_resolve(runId="r1", validCandidates=cands))
    assert len(out["resolvedEdges"]) == 1
    assert out["count"] == 1


def test_langgraph_resolve_llm_error_returns_error_key(monkeypatch):
    def raise_err(**kw): raise RuntimeError("LLM timeout")
    monkeypatch.setattr(IN._llm, "call_tier_json", raise_err)
    cands = [{"vertexId": "at://v1", "label": "Corp A", "subjectKind": "company"}]
    out = asyncio.run(IN.task_intel_langgraph_resolve(runId="r1", validCandidates=cands))
    assert "error" in out
    assert out["resolvedEdges"] == []


# ─── task_intel_candidate_scan (mocked DB) ───────────────────────────────

def _make_fake_cursor(rows=None, fetchone_row=None):
    class FakeCur:
        def execute(self, sql, params=None): pass
        def fetchall(self): return rows or []
        def fetchone(self): return fetchone_row
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return FakeCur()


def test_candidate_scan_returns_candidates(monkeypatch):
    rows = [
        ("at://v1", "company", "acme", "Acme Corp", "LEI123", "US", '{"revenue":1e6}'),
    ]
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=rows))
    out = asyncio.run(IN.task_intel_candidate_scan(runId="r1", maxCandidates=5))
    assert out["count"] == 1
    assert out["candidates"][0]["label"] == "Acme Corp"


def test_candidate_scan_error_returns_error_key(monkeypatch):
    class ErrCur:
        def execute(self, sql, params=None): raise RuntimeError("DB error")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(IN, "sync_cursor", lambda: ErrCur())
    out = asyncio.run(IN.task_intel_candidate_scan())
    assert "error" in out
    assert out["candidates"] == []


# ─── task_intel_entity_resolve (mocked DB) ───────────────────────────────

def test_entity_resolve_empty_query_returns_empty():
    out = asyncio.run(IN.task_intel_entity_resolve(query=""))
    assert out["candidates"] == []
    assert out["count"] == 0


def test_entity_resolve_returns_matches(monkeypatch):
    rows = [("at://v1", "company", "acme", "Acme Corp", "LEI123", "US")]
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=rows))
    out = asyncio.run(IN.task_intel_entity_resolve(query="Acme"))
    assert out["count"] == 1
    assert out["candidates"][0]["label"] == "Acme Corp"


def test_entity_resolve_with_hints(monkeypatch):
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=[]))
    out = asyncio.run(IN.task_intel_entity_resolve(
        query="Tesla", entityKind="company",
        hints={"lei": "XYZLEI", "jurisdiction": "US"},
    ))
    assert out["count"] == 0


def test_entity_resolve_db_error_returns_error_key(monkeypatch):
    class ErrCur:
        def execute(self, sql, params=None): raise RuntimeError("DB error")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(IN, "sync_cursor", lambda: ErrCur())
    out = asyncio.run(IN.task_intel_entity_resolve(query="Acme"))
    assert "error" in out


# ─── task_intel_dependency_list (mocked DB) ──────────────────────────────

def test_dependency_list_empty_db(monkeypatch):
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=[]))
    out = asyncio.run(IN.task_intel_dependency_list())
    assert out["count"] == 0
    assert out["edges"] == []


def test_dependency_list_with_rows(monkeypatch):
    rows = [
        ("edge1", "at://v1", "at://v2", "OWNS", 0.9, "active", 1,
         '{"summary":"test"}', "run1", "2026-01-01"),
    ]
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=rows))
    out = asyncio.run(IN.task_intel_dependency_list(status="active"))
    assert out["count"] == 1
    assert out["edges"][0]["predicate"] == "OWNS"


def test_dependency_list_db_error(monkeypatch):
    class ErrCur:
        def execute(self, sql, params=None): raise RuntimeError("DB error")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(IN, "sync_cursor", lambda: ErrCur())
    out = asyncio.run(IN.task_intel_dependency_list())
    assert "error" in out


# ─── task_intel_dependency_explain (mocked DB) ───────────────────────────

def test_dependency_explain_not_found(monkeypatch):
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(fetchone_row=None))
    out = asyncio.run(IN.task_intel_dependency_explain(edgeId="edge_missing"))
    assert out["found"] is False
    assert "not found" in out["explanation"].lower()


def test_dependency_explain_found(monkeypatch):
    row = ("edge1", "at://v1", "at://v2", "OWNS", 0.9, "active",
           '{"summary":"Corp owns building"}', "run1")
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(fetchone_row=row))
    out = asyncio.run(IN.task_intel_dependency_explain(edgeId="edge1"))
    assert out["found"] is True
    assert "OWNS" in out["explanation"]


# ─── task_intel_graph_counterparty (mocked DB) ───────────────────────────

def test_counterparty_requires_subject(monkeypatch):
    out = asyncio.run(IN.task_intel_graph_counterparty(
        subjectVertexId="", lei=""
    ))
    assert "error" in out
    assert out["nodes"] == []


def test_counterparty_returns_graph(monkeypatch):
    rows = [
        ("edge1", "at://v1", "at://v2", "OWNS", 0.9, "Corp A", "Corp B"),
    ]
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=rows))
    out = asyncio.run(IN.task_intel_graph_counterparty(subjectVertexId="at://v1"))
    assert out["count"] == 1
    assert len(out["nodes"]) == 2


def test_counterparty_db_error(monkeypatch):
    class ErrCur:
        def execute(self, sql, params=None): raise RuntimeError("DB error")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(IN, "sync_cursor", lambda: ErrCur())
    out = asyncio.run(IN.task_intel_graph_counterparty(subjectVertexId="at://v1"))
    assert "error" in out


# ─── task_intel_graph_building_ownership (mocked DB) ─────────────────────

def test_building_ownership_requires_building_or_lei():
    out = asyncio.run(IN.task_intel_graph_building_ownership(
        buildingVertexId="", lei=""
    ))
    assert "error" in out
    assert out["chain"] == []


def test_building_ownership_returns_chain(monkeypatch):
    rows = [
        ("edge1", "at://owner", "at://building", "OWNS", 0.95, "Owner Corp", "LEI001"),
    ]
    monkeypatch.setattr(IN, "sync_cursor", lambda: _make_fake_cursor(rows=rows))
    out = asyncio.run(IN.task_intel_graph_building_ownership(buildingVertexId="at://building"))
    assert out["count"] == 1
    assert out["chain"][0]["relation"] == "OWNS"


# ─── register ─────────────────────────────────────────────────────────────

def test_register_exposes_ten_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    IN.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "intel.run.create",
        "intel.candidate.scan",
        "intel.owl.validate",
        "intel.langgraph.resolve",
        "intel.edge.materialize",
        "intel.entity.resolve",
        "intel.dependency.list",
        "intel.dependency.explain",
        "intel.graph.counterparty",
        "intel.graph.buildingOwnership",
    }
