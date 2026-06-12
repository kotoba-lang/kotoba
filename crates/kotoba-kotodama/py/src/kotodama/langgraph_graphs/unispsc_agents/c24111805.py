# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111805 — Tank (segment 24).

Bespoke logic for managing storage tank specifications, pressure ratings,
and structural certification within the material handling segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111805"
UNISPSC_TITLE = "Tank"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Tank storage systems
    capacity_liters: float
    material_type: str
    pressure_rating_psi: float
    is_certified: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material compatibility for the tank."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 0))
    material = str(inp.get("material", "Carbon Steel"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "capacity_liters": capacity,
        "material_type": material,
    }


def calculate_load_limits(state: State) -> dict[str, Any]:
    """Calculates safe operating pressure based on material properties and volume."""
    material = state.get("material_type", "")
    capacity = state.get("capacity_liters", 0)

    # Heuristic pressure rating logic based on industrial standards
    base_pressure = 150.0 if "steel" in material.lower() else 45.0
    # Larger tanks typically have lower pressure tolerances in this model
    pressure = max(10.0, base_pressure - (capacity / 500.0))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_limits"],
        "pressure_rating_psi": pressure,
    }


def certify_vessel(state: State) -> dict[str, Any]:
    """Finalizes tank metadata and issues a structural certification record."""
    capacity = state.get("capacity_liters", 0)
    pressure = state.get("pressure_rating_psi", 0)
    certified = capacity > 0 and pressure > 0

    return {
        "log": [f"{UNISPSC_CODE}:certify_vessel"],
        "is_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "active" if certified else "pending",
            "technical_specs": {
                "capacity_l": capacity,
                "max_operating_pressure_psi": round(pressure, 2),
                "primary_material": state.get("material_type"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("calculate", calculate_load_limits)
_g.add_node("certify", certify_vessel)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
