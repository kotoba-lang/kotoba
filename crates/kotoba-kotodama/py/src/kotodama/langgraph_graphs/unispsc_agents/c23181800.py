# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181800 — Machine Maintenance (segment 23).

This bespoke LangGraph agent handles state transitions for industrial machine
maintenance workflows, including inspection, diagnostic repair simulation,
and final reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181800"
UNISPSC_TITLE = "Machine Maintenance"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields
    machine_id: str
    maintenance_type: str
    health_score: int
    parts_replaced: list[str]


def inspect_machine(state: State) -> dict[str, Any]:
    """Analyze machine input and determine current health status."""
    inp = state.get("input") or {}
    machine_id = inp.get("machine_id", "UNKNOWN-000")
    # Default to 75 if not provided, simulating an inspection result
    initial_health = inp.get("health_reading", 75)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_machine:{machine_id}"],
        "machine_id": machine_id,
        "health_score": initial_health,
        "maintenance_type": "PREVENTATIVE" if initial_health > 80 else "CORRECTIVE",
    }


def perform_maintenance(state: State) -> dict[str, Any]:
    """Execute maintenance tasks based on machine health."""
    health = state.get("health_score", 0)
    replaced = []
    new_health = health

    if health < 80:
        replaced.append("bearing_seal")
        replaced.append("hydraulic_filter")
        new_health = 95
    else:
        replaced.append("lubricant_additive")
        new_health = 100

    return {
        "log": [f"{UNISPSC_CODE}:perform_maintenance:{len(replaced)}_parts_serviced"],
        "parts_replaced": replaced,
        "health_score": new_health,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Compile final maintenance metrics and generate result object."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "machine_id": state.get("machine_id"),
            "final_health": state.get("health_score"),
            "parts_summary": state.get("parts_replaced"),
            "did": UNISPSC_DID,
            "status": "COMPLETED",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_machine)
_g.add_node("maintain", perform_maintenance)
_g.add_node("report", finalize_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "maintain")
_g.add_edge("maintain", "report")
_g.add_edge("report", END)

graph = _g.compile()
