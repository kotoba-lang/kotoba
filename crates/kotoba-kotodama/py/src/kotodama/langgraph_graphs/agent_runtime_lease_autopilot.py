"""
agent.runtime.leaseAutopilot — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `agent_runtime_lease_autopilot` (R/PT15M).

Graph:
  START → autopilot_tick → END
"""

from __future__ import annotations

from typing import TypedDict


class AgentRuntimeLeaseAutopilotState(TypedDict, total=False):
    ok: bool
    error: str | None


def autopilot_tick(state: AgentRuntimeLeaseAutopilotState) -> dict:
    from kotodama.primitives.agent_economy import task_agent_runtime_autopilot_tick

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_agent_runtime_autopilot_tick(**kwargs)
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AgentRuntimeLeaseAutopilotState)
    builder.add_node("autopilot_tick", autopilot_tick)
    builder.set_entry_point("autopilot_tick")
    builder.add_edge("autopilot_tick", END)
    return builder.compile()
