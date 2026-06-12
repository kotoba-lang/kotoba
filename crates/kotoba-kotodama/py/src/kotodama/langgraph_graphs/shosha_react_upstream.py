"""
shosha.reactToUpstream — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `shosha_react_to_upstream` (R/PT5M).
Triggered by K8s CronJob (every 5 minutes) via POST /runs.

Graph:
  START → scan_upstream → emit_audit → END

State:
  reactionsEmitted   int   reaction rows written (output)
  recordsScanned     int   upstream records examined (output)
  ok                 bool  overall success flag (output)
  error              str   error message if ok=False (output)
"""

from __future__ import annotations

import asyncio
import uuid
import time as _time
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
# ── State ──────────────────────────────────────────────────────────────

class ShoshaReactUpstreamState(TypedDict, total=False):
    reactionsEmitted: int
    recordsScanned: int
    ok: bool
    error: str | None


# ── Nodes ─────────────────────────────────────────────────────────────

def scan_upstream(state: ShoshaReactUpstreamState) -> dict:
    """Scan upstream actor commits and emit LLM-synthesised reactions."""
    from kotodama.primitives.shosha import task_shosha_reactive_scan_upstream

    try:
        result = asyncio.run(task_shosha_reactive_scan_upstream())
        return {
            "reactionsEmitted": result.get("reactions", 0),
            "recordsScanned": result.get("scanned", 0),
            "ok": True,
        }
    except Exception as e:
        return {"reactionsEmitted": 0, "recordsScanned": 0, "ok": False, "error": str(e)}


def emit_audit(state: ShoshaReactUpstreamState) -> dict:
    """Write OCEL audit row (non-fatal)."""
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", {
            "vertex_id": str(uuid.uuid4()),
            "repo": 'did:web:shosha.etzhayyim.com',
            "collection": 'com.etzhayyim.apps.shosha.reactToUpstream',
            "rkey": f'lg-{int(_time.time() * 1000)}',
            "action": 'create',
            "ts_ms": int(_time.time() * 1000),
            "record_json": f"""{{"reactionsEmitted":{state.get('reactionsEmitted', 0)},"recordsScanned":{state.get('recordsScanned', 0)},"ok":{str(state.get('ok', True)).lower()}}}""",
        })
    except Exception:
        pass
    return {}


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    """Build and compile the shosha reactToUpstream StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShoshaReactUpstreamState)
    builder.add_node("scan_upstream", scan_upstream)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("scan_upstream")
    builder.add_edge("scan_upstream", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
