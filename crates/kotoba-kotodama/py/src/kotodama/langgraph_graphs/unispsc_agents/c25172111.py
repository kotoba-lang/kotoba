# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172111 —  (segment 25).

Bespoke graph logic for Tire Valves (25172111). This agent manages the lifecycle
of a tire valve component, including specification validation and safety testing
to ensure compliance with vehicle transportation standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172111"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172111"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Tire Valves (UNISPSC 25172111)
    valve_model: str
    pressure_rating_psi: float
    material_standard: str
    is_pressure_stable: bool


def inspect_valve_spec(state: State) -> dict[str, Any]:
    """Inspects the tire valve specifications for industrial compliance."""
    inp = state.get("input") or {}
    model = inp.get("model", "TR-413-STD")
    rating = float(inp.get("rating", 65.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_valve_spec"],
        "valve_model": model,
        "pressure_rating_psi": rating,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Simulates a high-pressure seal integrity test on the valve component."""
    rating = state.get("pressure_rating_psi", 0.0)
    # Simulate integrity check: standard valves should handle up to 100 PSI safely
    integrity_pass = 0.0 < rating <= 150.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "is_pressure_stable": integrity_pass,
        "material_standard": "ASTM-V412",
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the component audit and emits the certification result."""
    passed = state.get("is_pressure_stable", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if passed else "REJECTED",
            "model": state.get("valve_model"),
            "material": state.get("material_standard"),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_valve_spec)
_g.add_node("verify", verify_integrity)
_g.add_node("certify", certify_component)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
