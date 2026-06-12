# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111605 — Generator (segment 26).

Bespoke graph logic for power generation equipment management. This agent
handles configuration, load simulation, and maintenance scheduling for
industrial and commercial generator units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111605"
UNISPSC_TITLE = "Generator"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Generator
    power_rating_kva: float
    fuel_type: str
    runtime_hours: float
    load_percent: float
    maintenance_required: bool


def configure_specs(state: State) -> dict[str, Any]:
    """Extract and validate generator specifications from input."""
    inp = state.get("input") or {}
    rating = float(inp.get("kva", 500.0))
    fuel = str(inp.get("fuel", "diesel"))
    runtime = float(inp.get("hours", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:configure_specs -> {rating}kVA {fuel}"],
        "power_rating_kva": rating,
        "fuel_type": fuel,
        "runtime_hours": runtime,
    }


def analyze_load(state: State) -> dict[str, Any]:
    """Simulate load analysis and determine maintenance urgency."""
    inp = state.get("input") or {}
    current_load = float(inp.get("current_load_kw", 0.0))
    capacity = state.get("power_rating_kva", 1.0)

    load_pct = (current_load / capacity) * 100
    runtime = state.get("runtime_hours", 0.0)
    needs_service = runtime > 500.0 or load_pct > 110.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load -> {load_pct:.1f}% load"],
        "load_percent": load_pct,
        "maintenance_required": needs_service,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generate the final status report for the generator actor."""
    status = "OVERLOADED" if state.get("load_percent", 0) > 100 else "OPERATIONAL"
    if state.get("maintenance_required"):
        status += " (SERVICE REQUIRED)"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": status,
            "metrics": {
                "kva": state.get("power_rating_kva"),
                "fuel": state.get("fuel_type"),
                "hours": state.get("runtime_hours"),
                "efficiency_pct": 92.5 if state.get("fuel_type") == "diesel" else 88.0,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("configure_specs", configure_specs)
_g.add_node("analyze_load", analyze_load)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "configure_specs")
_g.add_edge("configure_specs", "analyze_load")
_g.add_edge("analyze_load", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
