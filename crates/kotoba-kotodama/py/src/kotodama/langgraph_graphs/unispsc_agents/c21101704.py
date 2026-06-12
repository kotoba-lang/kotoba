# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101704 — Tractor (segment 21).

Bespoke logic for managing tractor operational state, maintenance checks,
and work assignment. This agent handles the lifecycle of a tractor unit
from pre-operational inspection to work completion.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101704"
UNISPSC_TITLE = "Tractor"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Tractor
    engine_status: str
    fuel_level: float
    hours_of_operation: int
    implement_attached: str


def pre_operational_check(state: State) -> dict[str, Any]:
    """Inspects engine and fuel levels before starting work."""
    inp = state.get("input") or {}
    fuel = inp.get("initial_fuel", 100.0)
    hours = inp.get("initial_hours", 1250)

    status = "nominal" if fuel > 15.0 else "low_fuel_warning"

    return {
        "log": [f"{UNISPSC_CODE}:pre_operational_check - status: {status}"],
        "fuel_level": fuel,
        "hours_of_operation": hours,
        "engine_status": status,
    }


def attach_implement(state: State) -> dict[str, Any]:
    """Attaches required machinery (e.g., plow, trailer) based on input."""
    inp = state.get("input") or {}
    implement = inp.get("required_implement", "generic_hitch")

    return {
        "log": [f"{UNISPSC_CODE}:attach_implement - {implement}"],
        "implement_attached": implement,
    }


def perform_work(state: State) -> dict[str, Any]:
    """Executes the task and updates tractor wear/fuel usage."""
    current_fuel = state.get("fuel_level", 0.0)
    current_hours = state.get("hours_of_operation", 0)

    # Simulate usage
    new_fuel = max(0.0, current_fuel - 10.5)
    new_hours = current_hours + 4

    return {
        "log": [f"{UNISPSC_CODE}:perform_work - fuel used: 10.5, hours added: 4"],
        "fuel_level": new_fuel,
        "hours_of_operation": new_hours,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "final_fuel": new_fuel,
            "final_hours": new_hours,
            "implement": state.get("implement_attached"),
            "status": "work_completed_successfully",
        },
    }


_g = StateGraph(State)
_g.add_node("pre_operational_check", pre_operational_check)
_g.add_node("attach_implement", attach_implement)
_g.add_node("perform_work", perform_work)

_g.add_edge(START, "pre_operational_check")
_g.add_edge("pre_operational_check", "attach_implement")
_g.add_edge("attach_implement", "perform_work")
_g.add_edge("perform_work", END)

graph = _g.compile()
