"""
shosha.refreshSanctionsList — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `shosha_refresh_sanctions_list` (daily 01:00 UTC).

Graph:
  START → refresh_ofac → refresh_un → END
"""

from __future__ import annotations

import asyncio
from typing import TypedDict


class ShoshaSanctionsState(TypedDict, total=False):
    ofac_inserted: int
    un_inserted: int
    ok: bool
    error: str | None


def refresh_ofac(state: ShoshaSanctionsState) -> dict:
    from kotodama.primitives.shosha import task_shosha_sanctions_refresh_ofac
    try:
        result = asyncio.run(task_shosha_sanctions_refresh_ofac())
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_un(state: ShoshaSanctionsState) -> dict:
    from kotodama.primitives.shosha import task_shosha_sanctions_refresh_un
    try:
        result = asyncio.run(task_shosha_sanctions_refresh_un())
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShoshaSanctionsState)
    builder.add_node("refresh_ofac", refresh_ofac)
    builder.add_node("refresh_un", refresh_un)
    builder.set_entry_point("refresh_ofac")
    builder.add_edge("refresh_ofac", "refresh_un")
    builder.add_edge("refresh_un", END)
    return builder.compile()
