# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141501 — Industrial tractors (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141501"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Industrial tractors
    battery_level: float
    towing_load_kg: float
    maintenance_cleared: bool
    assigned_terminal: str
    safety_interlock_active: bool


def pre_flight_inspection(state: State) -> dict[str, Any]:
    """Verify battery levels and maintenance records before operation."""
    inp = state.get("input") or {}
    battery = float(inp.get("battery_level", 100.0))
    maint = bool(inp.get("maintenance_cleared", True))

    status = "READY" if battery > 20.0 and maint else "RECHARGE_REQUIRED"
    return {
        "log": [f"{UNISPSC_CODE}:inspection_complete:{status}"],
        "battery_level": battery,
        "maintenance_cleared": maint,
        "safety_interlock_active": True,
    }


def validate_load(state: State) -> dict[str, Any]:
    """Ensure the towing load does not exceed the industrial tractor's capacity."""
    inp = state.get("input") or {}
    load = float(inp.get("load_kg", 0.0))
    # Standard industrial tractor capacity limit check (e.g. 5000kg)
    capacity_ok = load <= 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:load_validated:{capacity_ok}"],
        "towing_load_kg": load,
    }


def dispatch(state: State) -> dict[str, Any]:
    """Finalize dispatch to the assigned terminal if all conditions are met."""
    inp = state.get("input") or {}
    terminal = str(inp.get("terminal", "LOGISTICS_HUB_A"))

    ready = state.get("battery_level", 0.0) > 20.0 and state.get("maintenance_cleared", False)
    load_ok = state.get("towing_load_kg", 0.0) <= 5000.0
    interlock = state.get("safety_interlock_active", False)

    operational_success = ready and load_ok and interlock

    return {
        "log": [f"{UNISPSC_CODE}:dispatched_to_{terminal}"],
        "assigned_terminal": terminal,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "dispatch_successful": operational_success,
            "terminal_assignment": terminal,
            "ok": operational_success,
        },
    }


_g = StateGraph(State)
_g.add_node("pre_flight_inspection", pre_flight_inspection)
_g.add_node("validate_load", validate_load)
_g.add_node("dispatch", dispatch)

_g.add_edge(START, "pre_flight_inspection")
_g.add_edge("pre_flight_inspection", "validate_load")
_g.add_edge("validate_load", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
