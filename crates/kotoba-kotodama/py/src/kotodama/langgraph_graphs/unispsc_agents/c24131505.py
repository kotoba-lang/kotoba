# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131505 — Refrig Vessel (segment 24).

Bespoke graph for managing refrigerated vessel specifications and integrity checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131505"
UNISPSC_TITLE = "Refrig Vessel"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Refrigerated Vessel
    vessel_capacity_liters: float
    refrigerant_type: str
    internal_pressure_psi: float
    is_sealed: bool
    coolant_level_percent: float


def initialize_vessel(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_vessel"],
        "vessel_capacity_liters": float(inp.get("capacity", 500.0)),
        "refrigerant_type": str(inp.get("refrigerant", "Liquid Nitrogen")),
        "coolant_level_percent": 100.0,
    }


def perform_integrity_check(state: State) -> dict[str, Any]:
    # Simulate a pressure check based on the vessel type
    capacity = state.get("vessel_capacity_liters", 0.0)
    simulated_pressure = 14.7 + (capacity / 100.0)

    return {
        "log": [f"{UNISPSC_CODE}:perform_integrity_check"],
        "internal_pressure_psi": simulated_pressure,
        "is_sealed": simulated_pressure < 50.0,
    }


def certify_vessel(state: State) -> dict[str, Any]:
    sealed = state.get("is_sealed", False)
    pressure = state.get("internal_pressure_psi", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_vessel"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if sealed else "MAINTENANCE_REQUIRED",
            "telemetry": {
                "pressure": f"{pressure:.2f} PSI",
                "coolant": f"{state.get('coolant_level_percent')}%",
                "refrigerant": state.get("refrigerant_type"),
            },
            "ok": sealed,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_vessel", initialize_vessel)
_g.add_node("perform_integrity_check", perform_integrity_check)
_g.add_node("certify_vessel", certify_vessel)

_g.add_edge(START, "initialize_vessel")
_g.add_edge("initialize_vessel", "perform_integrity_check")
_g.add_edge("perform_integrity_check", "certify_vessel")
_g.add_edge("certify_vessel", END)

graph = _g.compile()
