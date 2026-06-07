"""
shosha.marketIntelligenceIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `shosha_market_intelligence_ingest` (R/PT1H).
Triggered by K8s CronJob (every hour) via POST /runs.

Graph:
  START → ingest_prices → ingest_freight → synth_market_views → emit_audit → END

State:
  priceRows         int   rows written for commodity / FX prices (output)
  freightRows       int   rows written for freight (output)
  marketViewRows    int   market views synthesised (output)
  priceSkipped      list  symbols that failed to fetch (output)
  ok                bool  overall success flag (output)
  error             str   error message if ok=False (output)
"""

from __future__ import annotations

import asyncio
import uuid
import time as _time
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
# ── State ──────────────────────────────────────────────────────────────

class ShoshaMarketIntelligenceState(TypedDict, total=False):
    priceRows: int
    freightRows: int
    marketViewRows: int
    priceSkipped: list[str]
    ok: bool
    error: str | None


# ── Nodes ─────────────────────────────────────────────────────────────

def ingest_prices(state: ShoshaMarketIntelligenceState) -> dict:
    """Fetch commodity prices from Yahoo Finance + FX from Frankfurter."""
    from kotodama.primitives.shosha import task_shosha_intel_ingest_prices

    try:
        result = asyncio.run(task_shosha_intel_ingest_prices())
        return {
            "priceRows": result.get("rows", 0),
            "priceSkipped": result.get("skipped", []),
        }
    except Exception as e:
        return {"priceRows": 0, "priceSkipped": [], "ok": False, "error": str(e)}


def ingest_freight(state: ShoshaMarketIntelligenceState) -> dict:
    """Ingest freight indices (Phase 1 stub)."""
    from kotodama.primitives.shosha import task_shosha_intel_ingest_freight

    try:
        result = asyncio.run(task_shosha_intel_ingest_freight())
        return {"freightRows": result.get("rows", 0)}
    except Exception as e:
        return {"freightRows": 0}


def synth_market_views(state: ShoshaMarketIntelligenceState) -> dict:
    """LLM-synthesise per-commodity market views from recent intel ticks."""
    from kotodama.primitives.shosha import task_shosha_market_view_synth

    try:
        result = asyncio.run(task_shosha_market_view_synth(lookbackHours=24))
        return {"marketViewRows": result.get("views", 0), "ok": True}
    except Exception as e:
        return {"marketViewRows": 0, "ok": False, "error": str(e)}


def emit_audit(state: ShoshaMarketIntelligenceState) -> dict:
    """Write OCEL audit row (non-fatal)."""
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", {
            "vertex_id": str(uuid.uuid4()),
            "repo": 'did:web:shosha.etzhayyim.com',
            "collection": 'com.etzhayyim.apps.shosha.marketIntelligenceIngest',
            "rkey": f'lg-{int(_time.time() * 1000)}',
            "action": 'create',
            "ts_ms": int(_time.time() * 1000),
            "record_json": f"""{{"priceRows":{state.get('priceRows', 0)},"freightRows":{state.get('freightRows', 0)},"marketViewRows":{state.get('marketViewRows', 0)},"ok":{str(state.get('ok', True)).lower()}}}""",
        })
    except Exception:
        pass
    return {}


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    """Build and compile the shosha marketIntelligenceIngest StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShoshaMarketIntelligenceState)
    builder.add_node("ingest_prices", ingest_prices)
    builder.add_node("ingest_freight", ingest_freight)
    builder.add_node("synth_market_views", synth_market_views)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("ingest_prices")
    builder.add_edge("ingest_prices", "ingest_freight")
    builder.add_edge("ingest_freight", "synth_market_views")
    builder.add_edge("synth_market_views", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
