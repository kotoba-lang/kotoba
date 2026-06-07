"""
shosha.dailyReport — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `shosha_daily_report`
(cron `0 0 22 * * ?` UTC = 07:00 JST).
Triggered by K8s CronJob (daily 22:00 UTC) via POST /runs.

Graph:
  START → compose_report → emit_audit → END

State:
  summary       str   composed daily report text (output)
  tradesCount   int   open/closed trades today (output)
  atRiskCount   int   at-risk trades flagged (output)
  todayPnlUsd   float today's realized P&L in USD (output)
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

class ShoshaDailyReportState(TypedDict, total=False):
    summary: str
    tradesCount: int
    atRiskCount: int
    todayPnlUsd: float
    ok: bool
    error: str | None


# ── Nodes ─────────────────────────────────────────────────────────────

def compose_report(state: ShoshaDailyReportState) -> dict:
    """Compose the daily trading report from MV data + LLM polish."""
    from kotodama.primitives.shosha import task_shosha_daily_report_compose

    try:
        result = asyncio.run(task_shosha_daily_report_compose())
        return {
            "summary": result.get("summary", ""),
            "tradesCount": result.get("tradesCount", 0),
            "atRiskCount": result.get("atRiskCount", 0),
            "todayPnlUsd": result.get("todayPnlUsd", 0.0),
            "ok": result.get("ok", True),
        }
    except Exception as e:
        return {
            "summary": "",
            "tradesCount": 0,
            "atRiskCount": 0,
            "todayPnlUsd": 0.0,
            "ok": False,
            "error": str(e),
        }


def emit_audit(state: ShoshaDailyReportState) -> dict:
    """Write OCEL audit row (non-fatal)."""
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", {
            "vertex_id": str(uuid.uuid4()),
            "repo": 'did:web:shosha.etzhayyim.com',
            "collection": 'com.etzhayyim.apps.shosha.dailyReport',
            "rkey": f'lg-{int(_time.time() * 1000)}',
            "action": 'create',
            "ts_ms": int(_time.time() * 1000),
            "record_json": f"""{{"tradesCount":{state.get('tradesCount', 0)},"atRiskCount":{state.get('atRiskCount', 0)},"todayPnlUsd":{state.get('todayPnlUsd', 0.0)},"ok":{str(state.get('ok', True)).lower()}}}""",
        })
    except Exception:
        pass
    return {}


# ── Graph factory ──────────────────────────────────────────────────────

def build_graph():
    """Build and compile the shosha dailyReport StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShoshaDailyReportState)
    builder.add_node("compose_report", compose_report)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("compose_report")
    builder.add_edge("compose_report", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
