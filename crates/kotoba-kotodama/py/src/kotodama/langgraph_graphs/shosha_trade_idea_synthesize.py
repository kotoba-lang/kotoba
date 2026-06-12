"""
shosha.tradeIdeaSynthesize — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `shosha_trade_idea_synthesize` (R/PT4H).
Triggered by K8s CronJob (every 4 hours) via POST /runs.

Graph:
  START → synth_ideas → emit_audit → END

State:
  ideaCount     int   trade ideas synthesised (output)
  summary       str   social summary text (output)
  ok            bool  overall success flag (output)
  error         str   error message if ok=False (output)
"""

from __future__ import annotations

import asyncio
import uuid
import time as _time
from typing import TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
# ── State ──────────────────────────────────────────────────────────────

class ShoshaTradeIdeaState(TypedDict, total=False):
    ideaCount: int
    summary: str
    ok: bool
    error: str | None


# ── Nodes ─────────────────────────────────────────────────────────────

def synth_ideas(state: ShoshaTradeIdeaState) -> dict:
    """LLM-synthesise trade ideas from current market views + exposure."""
    from kotodama.primitives.shosha import task_shosha_trade_synth

    try:
        result = asyncio.run(task_shosha_trade_synth())
        return {
            "ideaCount": result.get("ideaCount", 0),
            "summary": result.get("summary", ""),
            "ok": result.get("ok", True),
        }
    except Exception as e:
        return {"ideaCount": 0, "summary": "", "ok": False, "error": str(e)}


def emit_audit(state: ShoshaTradeIdeaState) -> dict:
    """Write OCEL audit row (non-fatal)."""
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", {
            "vertex_id": str(uuid.uuid4()),
            "repo": 'did:web:shosha.etzhayyim.com',
            "collection": 'com.etzhayyim.apps.shosha.tradeIdeaSynthesize',
            "rkey": f'lg-{int(_time.time() * 1000)}',
            "action": 'create',
            "ts_ms": int(_time.time() * 1000),
            "record_json": f"""{{"ideaCount":{state.get('ideaCount', 0)},"ok":{str(state.get('ok', True)).lower()}}}""",
        })
    except Exception:
        pass
    return {}


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    """Build and compile the shosha tradeIdeaSynthesize StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShoshaTradeIdeaState)
    builder.add_node("synth_ideas", synth_ideas)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("synth_ideas")
    builder.add_edge("synth_ideas", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
