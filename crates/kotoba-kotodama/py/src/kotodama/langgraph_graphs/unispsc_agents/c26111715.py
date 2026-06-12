# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111715"
UNISPSC_TITLE = "Battery"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111715"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Battery management
    voltage_nominal: float
    capacity_ah: float
    charge_level_pct: float
    safety_verified: bool
    state_of_health: float


def inspect_battery(state: State) -> dict[str, Any]:
    """Inspects physical and electrical specifications from input."""
    inp = state.get("input") or {}
    v_nom = float(inp.get("voltage", 12.0))
    cap = float(inp.get("capacity", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_battery"],
        "voltage_nominal": v_nom,
        "capacity_ah": cap,
        "safety_verified": v_nom > 0 and cap > 0
    }


def test_performance(state: State) -> dict[str, Any]:
    """Simulates performance testing and health evaluation."""
    inp = state.get("input") or {}
    cycle_count = int(inp.get("cycle_count", 0))

    # Calculate health based on lifecycle wear model
    health = max(0.0, min(1.0, 1.0 - (cycle_count / 1500.0)))

    return {
        "log": [f"{UNISPSC_CODE}:test_performance"],
        "state_of_health": health,
        "charge_level_pct": 100.0 * health
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Finalizes battery certification based on safety and health metrics."""
    is_safe = state.get("safety_verified", False)
    health = state.get("state_of_health", 0.0)

    passed = is_safe and health > 0.6
    status = "Certified" if passed else "Failed Inspection"

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "health_rating": f"{health:.2%}",
            "ok": passed
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_battery)
_g.add_node("test", test_performance)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
