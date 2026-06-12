# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242403 — Machine (segment 23).
Bespoke logic for industrial machine lifecycle management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242403"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242403"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for "Machine"
    power_status: str
    maintenance_mode: bool
    operating_temperature: float
    cycle_count: int


def startup_check(state: State) -> dict[str, Any]:
    """Initialize machine systems and verify power status."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "standard")
    is_maintenance = inp.get("maintenance", False)

    return {
        "log": [f"{UNISPSC_CODE}:startup_check -> mode={mode}"],
        "power_status": "ON",
        "maintenance_mode": is_maintenance,
        "operating_temperature": 25.5,
        "cycle_count": inp.get("initial_cycles", 0)
    }


def execute_cycle(state: State) -> dict[str, Any]:
    """Perform machine operation cycle and update telemetry."""
    if state.get("maintenance_mode"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_cycle -> skipped (maintenance mode active)"],
            "power_status": "IDLE"
        }

    current_cycles = state.get("cycle_count", 0)
    current_temp = state.get("operating_temperature", 25.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_cycle -> incrementing cycle count"],
        "cycle_count": current_cycles + 1,
        "operating_temperature": current_temp + 5.2,
        "power_status": "OPERATING"
    }


def shutdown_report(state: State) -> dict[str, Any]:
    """Generate final machine state report and power down."""
    cycle_count = state.get("cycle_count", 0)
    temp = state.get("operating_temperature", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:shutdown_report"],
        "power_status": "OFF",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "final_cycle_count": cycle_count,
            "final_temperature": temp,
            "status": "COMPLETED" if cycle_count > 0 else "MAINTENANCE_IDLE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("startup_check", startup_check)
_g.add_node("execute_cycle", execute_cycle)
_g.add_node("shutdown_report", shutdown_report)

_g.add_edge(START, "startup_check")
_g.add_edge("startup_check", "execute_cycle")
_g.add_edge("execute_cycle", "shutdown_report")
_g.add_edge("shutdown_report", END)

graph = _g.compile()
