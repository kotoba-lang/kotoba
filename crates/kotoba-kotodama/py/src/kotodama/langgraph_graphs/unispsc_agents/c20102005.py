# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102005 — Drilling Component (segment 20).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102005"
UNISPSC_TITLE = "Drilling Component"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Drilling Component
    bit_material: str
    rated_pressure_psi: int
    operational_hours: float
    integrity_certified: bool


def inspect_component(state: State) -> dict[str, Any]:
    """Initial inspection of the drilling component specifications."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbide-steel")
    pressure = inp.get("pressure_limit", 15000)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_component"],
        "bit_material": material,
        "rated_pressure_psi": pressure,
    }


def validate_parameters(state: State) -> dict[str, Any]:
    """Validate operational parameters against component limits."""
    pressure = state.get("rated_pressure_psi", 0)
    # Basic validation logic for drilling integrity
    is_safe = pressure > 5000
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "operational_hours": 0.0,
        "integrity_certified": is_safe,
    }


def finalize_deployment(state: State) -> dict[str, Any]:
    """Finalize the component state for deployment readiness."""
    certified = state.get("integrity_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_deployment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "status": "DEPLOYMENT_READY" if certified else "REJECTED",
            "metadata": {
                "material": state.get("bit_material"),
                "pressure_rating": state.get("rated_pressure_psi"),
                "hours_logged": state.get("operational_hours"),
            },
            "ok": certified,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_component", inspect_component)
_g.add_node("validate_parameters", validate_parameters)
_g.add_node("finalize_deployment", finalize_deployment)

_g.add_edge(START, "inspect_component")
_g.add_edge("inspect_component", "validate_parameters")
_g.add_edge("validate_parameters", "finalize_deployment")
_g.add_edge("finalize_deployment", END)

graph = _g.compile()
