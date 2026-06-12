# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111712"
UNISPSC_TITLE = "Battery"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111712"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_v: float
    charge_percentage: int
    cycle_count: int
    health_status: str


def check_charge_levels(state: State) -> dict[str, Any]:
    """Inspects the battery's current charge and voltage state."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 12.6))
    charge = int(inp.get("charge_percentage", 100))

    # Simple logic to bound values
    charge = max(0, min(100, charge))

    return {
        "log": [f"{UNISPSC_CODE}:check_charge_levels"],
        "voltage_v": voltage,
        "charge_percentage": charge,
    }


def analyze_degradation(state: State) -> dict[str, Any]:
    """Calculates battery health based on lifecycle history."""
    inp = state.get("input") or {}
    cycles = int(inp.get("cycle_count", 0))

    if cycles < 300:
        health = "Excellent"
    elif cycles < 800:
        health = "Good"
    elif cycles < 1500:
        health = "Fair"
    else:
        health = "Replace"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_degradation"],
        "cycle_count": cycles,
        "health_status": health,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Compiles the final state report for the battery actor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "voltage": f"{state.get('voltage_v')}V",
                "charge": f"{state.get('charge_percentage')}%",
                "cycles": state.get("cycle_count"),
                "health": state.get("health_status"),
            },
            "operational_integrity": state.get("health_status") != "Replace",
        },
    }


_g = StateGraph(State)

_g.add_node("check_charge_levels", check_charge_levels)
_g.add_node("analyze_degradation", analyze_degradation)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "check_charge_levels")
_g.add_edge("check_charge_levels", "analyze_degradation")
_g.add_edge("analyze_degradation", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
