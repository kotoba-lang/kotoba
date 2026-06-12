# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201601 — Aircraft (segment 25).

Bespoke graph logic for aircraft lifecycle management, including pre-flight
checks, engine diagnostics, and flight readiness certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201601"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Aircraft
    tail_number: str
    fuel_level_pct: float
    engine_status: str
    is_flight_ready: bool


def pre_flight_check(state: State) -> dict[str, Any]:
    """Initializes aircraft metadata and performs initial fuel level check."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "N00000")
    fuel = float(inp.get("fuel_level", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:pre_flight_check tail={tail} fuel={fuel}%"],
        "tail_number": tail,
        "fuel_level_pct": fuel,
    }


def engine_diagnostic(state: State) -> dict[str, Any]:
    """Evaluates engine status based on fuel levels and simulated diagnostics."""
    fuel = state.get("fuel_level_pct", 0.0)
    # Simple logic: fuel below 20% is a critical failure for departure
    status = "NOMINAL" if fuel >= 20.0 else "LOW_FUEL_CRITICAL"
    return {
        "log": [f"{UNISPSC_CODE}:engine_diagnostic status={status}"],
        "engine_status": status,
    }


def flight_readiness_approval(state: State) -> dict[str, Any]:
    """Finalizes the inspection and issues a flight readiness certificate."""
    status = state.get("engine_status")
    ready = status == "NOMINAL"
    return {
        "log": [f"{UNISPSC_CODE}:flight_readiness_approval ready={ready}"],
        "is_flight_ready": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "tail_number": state.get("tail_number"),
            "engine_status": status,
            "is_flight_ready": ready,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("pre_flight", pre_flight_check)
_g.add_node("diagnostic", engine_diagnostic)
_g.add_node("approval", flight_readiness_approval)

_g.add_edge(START, "pre_flight")
_g.add_edge("pre_flight", "diagnostic")
_g.add_edge("diagnostic", "approval")
_g.add_edge("approval", END)

graph = _g.compile()
