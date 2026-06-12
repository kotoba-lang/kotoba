"""
shinshi.seedGapFill — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `shinshi_seed_gap_fill` (R/PT4H).
Triggered by K8s CronJob (every 4 hours) via POST /runs.

Graph:
  START → find_incomplete → (conditional)
    if slugs empty → emit_audit → END
    else           → bulk_seed  → emit_audit → END

State:
  slugs           list[str]  incomplete model slugs (intermediate)
  totalIncomplete int        total count of incomplete models (intermediate)
  scenesPosted    int        scenes posted this run (output)
  ok              bool       overall success flag (output)
  error           str        error message if ok=False (output)
"""

from __future__ import annotations

import asyncio
import uuid
import time as _time
from typing import TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
_SHINSHI_ACTOR = "did:web:sh1n5h1x.etzhayyim.com"


# ── State ──────────────────────────────────────────────────────────────

class ShinshiSeedGapFillState(TypedDict, total=False):
    slugs: list
    totalIncomplete: int
    scenesPosted: int
    ok: bool
    error: str | None


# ── Nodes ─────────────────────────────────────────────────────────────

def find_incomplete(state: ShinshiSeedGapFillState) -> dict:
    """Find shinshi model slugs with fewer than 5 image posts."""
    from kotodama.primitives.shinshi_image import task_shinshi_coverage_find_incomplete

    try:
        result = asyncio.run(task_shinshi_coverage_find_incomplete())
        return {
            "slugs": result.get("slugs", []),
            "totalIncomplete": result.get("totalIncomplete", 0),
            "ok": True,
        }
    except Exception as e:
        return {"slugs": [], "totalIncomplete": 0, "ok": False, "error": str(e)}


def bulk_seed(state: ShinshiSeedGapFillState) -> dict:
    """Bulk seed up to 3 incomplete models with 5 scenes each."""
    from kotodama.primitives.shinshi_image import task_shinshi_scene_bulk_seed

    slugs = state.get("slugs", [])
    try:
        result = asyncio.run(
            task_shinshi_scene_bulk_seed(
                slugs=slugs[:3],
                skipIfExisting=True,
            )
        )
        total_posted = sum(
            r.get("scenesPosted", 0) for r in (result.get("results") or [])
        )
        return {"scenesPosted": total_posted, "ok": result.get("ok", True)}
    except Exception as e:
        return {"scenesPosted": 0, "ok": False, "error": str(e)}


def emit_audit(state: ShinshiSeedGapFillState) -> dict:
    """Write OCEL audit row (non-fatal)."""
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", {
            "vertex_id": str(uuid.uuid4()),
            "repo": _SHINSHI_ACTOR,
            "collection": 'com.etzhayyim.apps.shinshi.seedGapFill',
            "rkey": f'lg-{int(_time.time() * 1000)}',
            "action": 'create',
            "ts_ms": int(_time.time() * 1000),
            "record_json": f"""{{"totalIncomplete":{state.get('totalIncomplete', 0)},"scenesPosted":{state.get('scenesPosted', 0)},"ok":{str(state.get('ok', True)).lower()}}}""",
        })
    except Exception:
        pass
    return {}


# ── Routing ───────────────────────────────────────────────────────────

def _route_after_find(state: ShinshiSeedGapFillState) -> str:
    slugs = state.get("slugs", [])
    if not slugs or state.get("ok") is False:
        return "emit_audit"
    return "bulk_seed"


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    """Build and compile the shinshi seedGapFill StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShinshiSeedGapFillState)
    builder.add_node("find_incomplete", find_incomplete)
    builder.add_node("bulk_seed", bulk_seed)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("find_incomplete")
    builder.add_conditional_edges(
        "find_incomplete",
        _route_after_find,
        {"bulk_seed": "bulk_seed", "emit_audit": "emit_audit"},
    )
    builder.add_edge("bulk_seed", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
