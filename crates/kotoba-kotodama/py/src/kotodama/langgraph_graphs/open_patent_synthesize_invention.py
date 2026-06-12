"""
openPatent.synthesizeInvention — LangGraph Pregel (ADR-2605080600 Phase 5).

Triggered weekly by K8s CronJob (Monday 03:00 UTC) via POST /runs.

Graph:
  START → gather_trends → synthesize_seeds → search_prior_art
        → assess_novelty → flag_for_review → emit_audit → END

HITL boundary: flag_for_review sets novelty_status='review'.
Claim drafting and patent filing are human-only steps performed outside
this system.

State keys:
  techDomainLimit   int  (input)
  seedsPerDomain    int  (input)
  noveltyThreshold  int  (input, default 60)
  dryRun            bool (input)
  tech_domains      list[dict]
  raw_seeds         list[dict]
  seeds_with_art    list[dict]  [{seed, prior_art, assessment}]
  seedsGenerated    int  (output)
  seedsFlagged      int  (output)
  ok                bool (output)
  error             str  (output)
"""

from __future__ import annotations

import time as _time
import uuid
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
class OpenPatentSynthesizeState(TypedDict, total=False):
    techDomainLimit: int | None
    seedsPerDomain: int | None
    noveltyThreshold: int | None
    dryRun: bool | None
    tech_domains: list[dict[str, Any]]
    raw_seeds: list[dict[str, Any]]
    seeds_with_art: list[dict[str, Any]]
    seedsGenerated: int
    seedsFlagged: int
    ok: bool
    error: str | None


# ── Nodes ──────────────────────────────────────────────────────────────

def gather_trends(state: OpenPatentSynthesizeState) -> dict:
    from kotodama.primitives.open_patent_generate import task_open_patent_gather_tech_trends

    limit = state.get("techDomainLimit") or 5
    try:
        domains = task_open_patent_gather_tech_trends(limit=limit)
        if not domains:
            return {"tech_domains": [], "ok": False, "error": "no_patent_corpus"}
        return {"tech_domains": domains, "ok": True}
    except Exception as exc:
        return {"tech_domains": [], "ok": False, "error": str(exc)}


def synthesize_seeds(state: OpenPatentSynthesizeState) -> dict:
    from kotodama.primitives.open_patent_generate import task_open_patent_generate_invention_seeds

    if not state.get("ok", True):
        return {}

    per_domain = state.get("seedsPerDomain") or 3
    domains = state.get("tech_domains") or []
    all_seeds: list[dict[str, Any]] = []

    for domain in domains:
        try:
            seeds = task_open_patent_generate_invention_seeds(
                tech_domain=domain["ipc_class"],
                sample_titles=domain.get("sample_titles") or [],
                count=per_domain,
            )
            all_seeds.extend(seeds)
        except Exception:
            pass

    return {"raw_seeds": all_seeds}


def search_prior_art(state: OpenPatentSynthesizeState) -> dict:
    from kotodama.primitives.open_patent_generate import task_open_patent_search_prior_art

    if not state.get("ok", True):
        return {}

    seeds = state.get("raw_seeds") or []
    enriched: list[dict[str, Any]] = []

    for seed in seeds:
        try:
            prior = task_open_patent_search_prior_art(
                title=seed.get("title", ""),
                summary=seed.get("summary", ""),
                ipc_class=seed.get("ipc_class", ""),
            )
        except Exception:
            prior = []
        enriched.append({"seed": seed, "prior_art": prior, "assessment": {}})

    return {"seeds_with_art": enriched}


def assess_novelty(state: OpenPatentSynthesizeState) -> dict:
    from kotodama.primitives.open_patent_generate import task_open_patent_assess_novelty

    if not state.get("ok", True):
        return {}

    enriched = state.get("seeds_with_art") or []
    updated: list[dict[str, Any]] = []

    for item in enriched:
        try:
            assessment = task_open_patent_assess_novelty(
                seed=item["seed"],
                prior_art=item["prior_art"],
            )
        except Exception as exc:
            assessment = {"novelty_score": 0, "reasoning": str(exc)}
        updated.append({**item, "assessment": assessment})

    return {"seeds_with_art": updated}


def flag_for_review(state: OpenPatentSynthesizeState) -> dict:
    """
    Persist seeds + novelty reports. Seeds with score >= threshold get
    novelty_status='review' (HITL boundary).
    """
    from kotodama.primitives.open_patent_generate import (
        task_open_patent_persist_seeds,
        task_open_patent_persist_novelty_report,
    )

    if state.get("dryRun"):
        items = state.get("seeds_with_art") or []
        threshold = state.get("noveltyThreshold") or 60
        flagged = sum(
            1 for it in items
            if it.get("assessment", {}).get("novelty_score", 0) >= threshold
        )
        return {"seedsGenerated": len(items), "seedsFlagged": flagged, "ok": True}

    items = state.get("seeds_with_art") or []
    threshold = state.get("noveltyThreshold") or 60

    seeds_to_persist = [it["seed"] for it in items]
    try:
        task_open_patent_persist_seeds(seeds_to_persist)
    except Exception as exc:
        return {"ok": False, "error": f"persist_seeds: {exc}"}

    flagged = 0
    for item in items:
        seed_vid = item["seed"]["vertex_id"]
        try:
            task_open_patent_persist_novelty_report(
                seed_vid=seed_vid,
                prior_art=item["prior_art"],
                assessment=item["assessment"],
            )
            if item["assessment"].get("novelty_score", 0) >= threshold:
                flagged += 1
        except Exception:
            pass

    return {"seedsGenerated": len(items), "seedsFlagged": flagged, "ok": True}


def emit_audit(state: OpenPatentSynthesizeState) -> dict:
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", {
            "vertex_id": str(uuid.uuid4()),
            "repo": 'did:web:open-patent.etzhayyim.com',
            "collection": 'com.etzhayyim.apps.openPatent.synthesizeInvention',
            "rkey": f'lg-{int(_time.time() * 1000)}',
            "action": 'create',
            "ts_ms": int(_time.time() * 1000),
            "record_json": f"""{{"seedsGenerated":{state.get('seedsGenerated', 0)},"seedsFlagged":{state.get('seedsFlagged', 0)},"ok":{str(state.get('ok', True)).lower()}}}""",
        })
    except Exception:
        pass
    return {}


# ── Routing ────────────────────────────────────────────────────────────

def _has_corpus_gate(state: OpenPatentSynthesizeState) -> str:
    if not state.get("tech_domains"):
        return "emit_audit"
    return "synthesize_seeds"


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(OpenPatentSynthesizeState)
    builder.add_node("gather_trends", gather_trends)
    builder.add_node("synthesize_seeds", synthesize_seeds)
    builder.add_node("search_prior_art", search_prior_art)
    builder.add_node("assess_novelty", assess_novelty)
    builder.add_node("flag_for_review", flag_for_review)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("gather_trends")
    builder.add_conditional_edges(
        "gather_trends",
        _has_corpus_gate,
        {"synthesize_seeds": "synthesize_seeds", "emit_audit": "emit_audit"},
    )
    builder.add_edge("synthesize_seeds", "search_prior_art")
    builder.add_edge("search_prior_art", "assess_novelty")
    builder.add_edge("assess_novelty", "flag_for_review")
    builder.add_edge("flag_for_review", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
