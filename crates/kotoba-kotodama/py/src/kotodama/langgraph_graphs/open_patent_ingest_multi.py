"""
openPatent.ingestMulti — LangGraph multi-jurisdiction enrichment coordinator.

ADR-2605080600 Phase 5.  Triggered daily (02:00 UTC) via K8s CronJob.

Follow-based rule: this graph does NOT call external APIs.  It processes
patent data already received from patent.etzhayyim.com (and jurisdiction sub-actors)
via AT Protocol subscribeRepos firehose and written to vertex_open_patent_*.

Graph:
  START → check_backlog → enrich_epo → enrich_jpo → enrich_wipo
        → emit_audit → END

  check_backlog → emit_audit (short-circuit when nothing to do)

State:
  jurisdictions     list[str]  input: ['us','ep','jp','wo']. default: all
  batchSize         int        input: default 100
  backlog           dict       {jurisdiction: count}
  results           list[dict] per-jurisdiction enrichment results
  ok                bool
  error             str | None
"""

from __future__ import annotations

import time as _time
import uuid
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client


class OpenPatentIngestMultiState(TypedDict, total=False):
    jurisdictions: list[str] | None
    batchSize: int | None
    backlog: dict[str, int]
    results: list[dict[str, Any]]
    ok: bool
    error: str | None


# ── Nodes ──────────────────────────────────────────────────────────────

def check_backlog(state: OpenPatentIngestMultiState) -> dict:
    """Count total patents per jurisdiction (fast scan, no correlated subquery)."""
    requested = state.get("jurisdictions") or ["us", "ep", "jp", "wo"]
    backlog: dict[str, int] = {}

    _kotoba = get_kotoba_client()
    for jur in requested:
        cc = jur.upper()
        row = _kotoba.select_first_where(
            "vertex_open_patent_patent",
            "jurisdiction",
            cc
        )
        backlog[jur] = 1 if row else 0

    return {"backlog": backlog, "ok": True}


def enrich_epo(state: OpenPatentIngestMultiState) -> dict:
    """
    Fill EPO OPS citations for US patents in the corpus.
    Calls the canonical EPO primitive from patent_ingest.py.
    """
    from kotodama.primitives.patent_ingest import task_patent_epo_ops_fill_citations

    jurs = state.get("jurisdictions") or ["us", "ep", "jp", "wo"]
    if "us" not in jurs and "ep" not in jurs:
        return {}

    batch = state.get("batchSize") or 100
    try:
        result = task_patent_epo_ops_fill_citations(batchSize=batch)
        return {
            "results": (state.get("results") or []) + [
                {"jurisdiction": "ep", **result}
            ]
        }
    except Exception as exc:
        return {
            "results": (state.get("results") or []) + [
                {"jurisdiction": "ep", "ok": False, "error": str(exc)}
            ]
        }


def enrich_jpo(state: OpenPatentIngestMultiState) -> dict:
    """
    JPO citation enrichment — reads AT records published by patent.etzhayyim.com:jp.
    Skeleton: requires patent.etzhayyim.com:jp to be publishing JP patent AT records.
    """
    jurs = state.get("jurisdictions") or ["us", "ep", "jp", "wo"]
    if "jp" not in jurs:
        return {}

    return {
        "results": (state.get("results") or []) + [
            {
                "jurisdiction": "jp",
                "skipped": True,
                "reason": "JPO enrichment pending patent.etzhayyim.com:jp actor",
                "ok": True,
            }
        ]
    }


def enrich_wipo(state: OpenPatentIngestMultiState) -> dict:
    """
    WIPO/CN/KR citation enrichment — skeleton awaiting upstream actor.
    """
    jurs = state.get("jurisdictions") or ["us", "ep", "jp", "wo"]
    skipped = [j for j in ["wo", "cn", "kr"] if j in jurs]
    if not skipped:
        return {}

    return {
        "results": (state.get("results") or []) + [
            {
                "jurisdiction": j,
                "skipped": True,
                "reason": f"{j.upper()} enrichment pending upstream actor",
                "ok": True,
            }
            for j in skipped
        ]
    }


def emit_audit(state: OpenPatentIngestMultiState) -> dict:
    results = state.get("results") or []
    citations_total = sum(
        r.get("citationsAdded", 0) or 0 for r in results
    )
    try:
        _kotoba = get_kotoba_client()
        row_data = {
            "vertex_id": str(uuid.uuid4()),
            "repo": "did:web:open-patent.etzhayyim.com",
            "collection": "com.etzhayyim.apps.openPatent.ingestMulti",
            "rkey": f"lg-{int(_time.time() * 1000)}",
            "action": "create",
            "ts_ms": int(_time.time() * 1000),
            "record_json": f'{{"citationsTotal":{citations_total},'
                           f'"jurisdictions":{len(results)},'
                           f'"ok":{str(state.get("ok", True)).lower()}}}',
        }
        _kotoba.insert_row("vertex_repo_commit", row_data)
    except Exception:
        pass
    return {}


# ── Routing ────────────────────────────────────────────────────────────

def _has_work_gate(state: OpenPatentIngestMultiState) -> str:
    backlog = state.get("backlog") or {}
    if sum(backlog.values()) == 0:
        return "emit_audit"
    return "enrich_epo"


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(OpenPatentIngestMultiState)
    builder.add_node("check_backlog", check_backlog)
    builder.add_node("enrich_epo", enrich_epo)
    builder.add_node("enrich_jpo", enrich_jpo)
    builder.add_node("enrich_wipo", enrich_wipo)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("check_backlog")
    builder.add_conditional_edges(
        "check_backlog",
        _has_work_gate,
        {"enrich_epo": "enrich_epo", "emit_audit": "emit_audit"},
    )
    builder.add_edge("enrich_epo", "enrich_jpo")
    builder.add_edge("enrich_jpo", "enrich_wipo")
    builder.add_edge("enrich_wipo", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
