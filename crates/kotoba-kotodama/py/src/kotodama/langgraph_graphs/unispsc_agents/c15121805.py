# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121805 — Aviation Fuel (segment 15).

Bespoke graph logic for Aviation Fuel quality control and distribution tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121805"
UNISPSC_TITLE = "Aviation Fuel"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Aviation Fuel
    fuel_type: str
    contamination_check: bool
    density_measured: float
    flash_point_celsius: float


def intake_specification(state: State) -> dict[str, Any]:
    """Analyzes the input request for specific fuel requirements."""
    inp = state.get("input") or {}
    fuel_type = inp.get("fuel_type", "Jet A-1")
    return {
        "log": [f"{UNISPSC_CODE}:intake_specification -> {fuel_type}"],
        "fuel_type": fuel_type,
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Simulates mandatory safety checks for aviation-grade fuel."""
    fuel_type = state.get("fuel_type", "")
    # Aviation grade check (Jet A, Jet A-1, Avgas 100LL etc.)
    is_aviation_grade = any(fuel_type.startswith(p) for p in ["Jet", "Avgas"])
    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance -> pass={is_aviation_grade}"],
        "contamination_check": is_aviation_grade,
        "density_measured": 804.0,  # kg/m3 at 15C
        "flash_point_celsius": 38.5,
    }


def dispatch_batch(state: State) -> dict[str, Any]:
    """Finalizes the fuel batch processing and prepares the result metadata."""
    passed = state.get("contamination_check", False)
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "fuel_type": state.get("fuel_type"),
            "status": "APPROVED" if passed else "REJECTED",
            "metrics": {
                "density": state.get("density_measured"),
                "flash_point": state.get("flash_point_celsius"),
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("intake_specification", intake_specification)
_g.add_node("quality_assurance", quality_assurance)
_g.add_node("dispatch_batch", dispatch_batch)

_g.add_edge(START, "intake_specification")
_g.add_edge("intake_specification", "quality_assurance")
_g.add_edge("quality_assurance", "dispatch_batch")
_g.add_edge("dispatch_batch", END)

graph = _g.compile()
