# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174103"
UNISPSC_TITLE = "Roof"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Vehicle Roof assembly
    roof_type: str  # e.g., Panoramic, Hardtop, Sunroof
    material_spec: str  # e.g., Aluminum, Carbon Fiber, Reinforced Glass
    sealant_integrity: float  # Quality metric 0.0 to 1.0
    installation_status: str  # Pending, In-Progress, Verified


def inspect_spec(state: State) -> dict[str, Any]:
    """Validates the input specifications for the vehicle roof component."""
    inp = state.get("input") or {}
    r_type = inp.get("roof_type", "Standard Hardtop")
    material = inp.get("material", "Steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec -> {r_type} using {material}"],
        "roof_type": r_type,
        "material_spec": material,
        "installation_status": "In-Progress",
    }


def apply_sealant(state: State) -> dict[str, Any]:
    """Simulates the application and testing of weather-stripping and sealants."""
    material = state.get("material_spec", "Steel")
    # Simulate varied integrity based on material compatibility
    integrity = 0.99 if material == "Carbon Fiber" else 0.95

    return {
        "log": [f"{UNISPSC_CODE}:apply_sealant -> calculated integrity: {integrity}"],
        "sealant_integrity": integrity,
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Final structural verification and data emission."""
    integrity = state.get("sealant_integrity", 0.0)
    passed = integrity >= 0.95

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_emit -> success: {passed}"],
        "installation_status": "Verified" if passed else "Failed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "type": state.get("roof_type"),
                "material": state.get("material_spec"),
                "integrity": integrity
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("apply_sealant", apply_sealant)
_g.add_node("verify_and_emit", verify_and_emit)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "apply_sealant")
_g.add_edge("apply_sealant", "verify_and_emit")
_g.add_edge("verify_and_emit", END)

graph = _g.compile()
