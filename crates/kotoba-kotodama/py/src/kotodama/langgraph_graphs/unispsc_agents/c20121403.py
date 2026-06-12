# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121403 — Motor.

This module provides bespoke LangGraph logic for managing motor data,
validating electrical requirements, and assessing efficiency ratings
within the oil and gas drilling equipment context.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121403"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121403"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Motor"
    voltage_rating: int
    current_load: float
    is_overheated: bool
    efficiency_score: float
    maintenance_required: bool


def ingest_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the motor unit."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 480)
    load = inp.get("load", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:ingest_specs"],
        "voltage_rating": voltage,
        "current_load": load,
        "maintenance_required": load > 110.0,
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates motor efficiency based on current load and voltage."""
    voltage = state.get("voltage_rating", 0)
    load = state.get("current_load", 0.0)

    # Simulated efficiency heuristic for drilling motors
    score = 0.94 if (400 <= voltage <= 520 and load < 85) else 0.82

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "efficiency_score": score,
        "is_overheated": load > 95.0,
    }


def package_results(state: State) -> dict[str, Any]:
    """Finalizes the state into a compliant result dictionary."""
    is_ok = not state.get("maintenance_required") and not state.get("is_overheated")

    return {
        "log": [f"{UNISPSC_CODE}:package_results"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "efficiency": state.get("efficiency_score"),
                "overheat_alert": state.get("is_overheated"),
                "voltage": state.get("voltage_rating"),
                "load": state.get("current_load"),
            },
            "ok": is_ok,
            "status": "operational" if is_ok else "alert_triggered",
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specs)
_g.add_node("analyze", analyze_performance)
_g.add_node("package", package_results)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "package")
_g.add_edge("package", END)

graph = _g.compile()
