# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151504 — Machine (segment 23).
Bespoke implementation for industrial machinery state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151504"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Machine"
    machine_id: str
    maintenance_interval_hours: int
    health_score: float
    runtime_hours: float


def initialize_machine(state: State) -> dict[str, Any]:
    """Sets the initial state of the machine actor based on telemetry input."""
    inp = state.get("input") or {}
    m_id = inp.get("machine_id", "M-GENERIC-001")
    runtime = float(inp.get("runtime_hours", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_machine(id={m_id}, runtime={runtime})"],
        "machine_id": m_id,
        "runtime_hours": runtime,
        "maintenance_interval_hours": 1000,
    }


def run_diagnostics(state: State) -> dict[str, Any]:
    """Performs simulated diagnostic checks on machine health metrics."""
    runtime = state.get("runtime_hours", 0.0)
    interval = state.get("maintenance_interval_hours", 1000)

    # Calculate health score: degradation increases as runtime approaches maintenance interval
    base_health = 100.0
    degradation = (runtime % interval) / interval * 15.0
    health = max(0.0, base_health - degradation)

    return {
        "log": [f"{UNISPSC_CODE}:run_diagnostics(computed_health={health:.2f})"],
        "health_score": health,
    }


def finalize_state(state: State) -> dict[str, Any]:
    """Prepares the final result and operational status report."""
    health = state.get("health_score", 0.0)
    m_id = state.get("machine_id", "N/A")
    runtime = state.get("runtime_hours", 0.0)

    status = "OPTIMAL" if health > 90 else "NOMINAL" if health > 75 else "ATTENTION_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_state(status={status})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "machine_id": m_id,
            "runtime_total": runtime,
            "health_score": health,
            "operational_status": status,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_machine)
_g.add_node("diagnostics", run_diagnostics)
_g.add_node("finalize", finalize_state)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "diagnostics")
_g.add_edge("diagnostics", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
