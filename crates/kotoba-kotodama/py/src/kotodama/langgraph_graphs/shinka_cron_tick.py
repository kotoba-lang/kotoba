"""
shinka.cronTick — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `shinka_cron_tick` (R/PT15M, v1+v2+v3).
Triggered by K8s CronJob (every 15 minutes) via POST /runs.

Graph:
  START → shinka_tick → END

State:
  actor           str   actor DID (input, default: did:web:yoro.etzhayyim.com)
  mood            str   tick mood output
  actions         list  actions taken during tick
  heartbeatWritten bool  whether heartbeat was written
  evolutionWritten bool  whether evolution was written
  tickMs          int   tick timestamp in ms
  ok              bool  overall success flag
  error           str   error message if ok=False
"""

from __future__ import annotations

import asyncio
from typing import Any
from typing import TypedDict

_DEFAULT_ACTOR = "did:web:yoro.etzhayyim.com"


class ShinkaCronTickState(TypedDict, total=False):
    actor: str
    mood: str | None
    actions: list[Any]
    heartbeatWritten: bool
    evolutionWritten: bool
    tickMs: int | None
    ok: bool
    error: str | None


def shinka_tick(state: ShinkaCronTickState) -> dict:
    """Call shinka_tick_actor SQL UDF for the target actor."""
    from kotodama.primitives.shinka import task_shinka_tick

    actor = state.get("actor") or _DEFAULT_ACTOR
    try:
        result = asyncio.run(task_shinka_tick(actor=actor))
        if "error" in result:
            return {"ok": False, "error": result["error"], "actor": actor}
        return {
            "actor": result.get("actor", actor),
            "mood": result.get("mood"),
            "actions": result.get("actions") or [],
            "heartbeatWritten": bool(result.get("heartbeatWritten")),
            "evolutionWritten": bool(result.get("evolutionWritten")),
            "tickMs": result.get("tickMs"),
            "ok": True,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "actor": actor}


def build_graph():
    """Build and compile the shinka cronTick StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(ShinkaCronTickState)
    builder.add_node("shinka_tick", shinka_tick)
    builder.set_entry_point("shinka_tick")
    builder.add_edge("shinka_tick", END)

    return builder.compile()
