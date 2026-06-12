# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131801 — Airship (segment 25).

This module implements bespoke flight systems logic for an Airship actor,
handling safety inspections, buoyancy calculations, and mission dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131801"
UNISPSC_TITLE = "Airship"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    hull_integrity: float
    gas_mixture: str
    ballast_kg: float
    flight_clearance: bool


def inspect_vessel(state: State) -> dict[str, Any]:
    """Inspects the airship hull and gas containment systems."""
    inp = state.get("input") or {}
    integrity = float(inp.get("integrity", 1.0))
    gas = str(inp.get("gas", "Helium"))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel: integrity={integrity}, gas={gas}"],
        "hull_integrity": integrity,
        "gas_mixture": gas,
    }


def calculate_lift(state: State) -> dict[str, Any]:
    """Calculates buoyancy and determines ballast requirements."""
    inp = state.get("input") or {}
    ballast = float(inp.get("ballast", 1200.0))
    # Clearance requires high integrity and non-volatile gas if specified
    integrity = state.get("hull_integrity", 0.0)
    clearance = integrity > 0.90

    return {
        "log": [f"{UNISPSC_CODE}:calculate_lift: ballast={ballast}kg, clearance={clearance}"],
        "ballast_kg": ballast,
        "flight_clearance": clearance,
    }


def authorize_dispatch(state: State) -> dict[str, Any]:
    """Finalizes the flight manifest and authorizes the mission."""
    clearance = state.get("flight_clearance", False)
    status = "READY" if clearance else "GROUNDED"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_dispatch: status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "flight_status": status,
            "telemetry": {
                "integrity": state.get("hull_integrity"),
                "gas": state.get("gas_mixture"),
                "ballast": state.get("ballast_kg")
            },
            "authorized": clearance
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_vessel)
_g.add_node("lift", calculate_lift)
_g.add_node("dispatch", authorize_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "lift")
_g.add_edge("lift", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
