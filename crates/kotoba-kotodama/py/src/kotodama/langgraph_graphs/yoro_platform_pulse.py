"""
yoro.platformPulse — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `yoro_platform_pulse` (R/PT4H, v1+v2).
Triggered by K8s CronJob (every 4 hours) via POST /runs.

Graph:
  START → platform_pulse → END

State:
  postUri         str   URI of the posted record (output)
  postText        str   text of the post (output)
  postsLast24h    int   posts in the last 24h (output)
  activeActors    int   active actor count (output)
  ok              bool  overall success flag (output)
  error           str   error message if ok=False (output)
"""

from __future__ import annotations

import asyncio
from typing import TypedDict


class YoroPlatformPulseState(TypedDict, total=False):
    postUri: str
    postText: str
    postsLast24h: int
    activeActors: int
    ok: bool
    error: str | None


def platform_pulse(state: YoroPlatformPulseState) -> dict:
    """Emit the yoro platform pulse post."""
    from kotodama.primitives.yoro_social import (
        task_yoro_social_platform_pulse_graph_fallback,
    )

    try:
        result = asyncio.run(
            task_yoro_social_platform_pulse_graph_fallback(
                postRepo="did:web:yoro.etzhayyim.com",
                flush=False,
            )
        )
        return {
            "postUri": result.get("uri", ""),
            "postText": result.get("text", ""),
            "postsLast24h": result.get("postsLast24h", 0),
            "activeActors": result.get("activeActors", 0),
            "ok": result.get("ok", True),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    """Build and compile the yoro platformPulse StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(YoroPlatformPulseState)
    builder.add_node("platform_pulse", platform_pulse)
    builder.set_entry_point("platform_pulse")
    builder.add_edge("platform_pulse", END)

    return builder.compile()
