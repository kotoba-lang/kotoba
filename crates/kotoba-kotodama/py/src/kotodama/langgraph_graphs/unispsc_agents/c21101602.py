# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101602 — Tractor (segment 21).

Bespoke LangGraph logic for managing tractor lifecycle, maintenance, and task scheduling.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101602"
UNISPSC_TITLE = "Tractor"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fuel_level: float
    engine_hours: float
    implement_type: str
    is_operational: bool


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Node: Inspect the tractor's physical and mechanical status."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel_level", 100.0))
    hours = float(inp.get("engine_hours", 0.0))

    operational = fuel > 5.0 and hours < 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle - fuel={fuel}%, hours={hours}"],
        "fuel_level": fuel,
        "engine_hours": hours,
        "is_operational": operational,
    }


def schedule_task(state: State) -> dict[str, Any]:
    """Node: Determine the task based on attached implements."""
    if not state.get("is_operational"):
        return {"log": [f"{UNISPSC_CODE}:schedule_task - tractor non-operational"]}

    inp = state.get("input") or {}
    implement = inp.get("implement", "none")

    task_log = f"task scheduled with {implement}" if implement != "none" else "idle - no implement"

    return {
        "log": [f"{UNISPSC_CODE}:schedule_task - {task_log}"],
        "implement_type": implement,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Node: Emit the final tractor state and task outcome."""
    operational = state.get("is_operational", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "operational": operational,
                "fuel": state.get("fuel_level"),
                "hours": state.get("engine_hours"),
                "implement": state.get("implement_type")
            },
            "status": "success" if operational else "maintenance_required"
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_vehicle)
_g.add_node("schedule", schedule_task)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "schedule")
_g.add_edge("schedule", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
