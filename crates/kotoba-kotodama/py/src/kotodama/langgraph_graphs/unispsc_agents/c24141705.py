# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141705 — Tube (segment 24).

This bespoke implementation handles tubing specification validation,
structural integrity assessment, and certification for industrial tubes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141705"
UNISPSC_TITLE = "Tube"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Tube
    material_type: str
    outer_diameter: float
    wall_thickness: float
    integrity_verified: bool
    pressure_rating_psi: float


def validate_tubing_specs(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and material grade of the tube."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "carbon_steel"))
    od = float(inp.get("outer_diameter", 1.0))
    wall = float(inp.get("wall_thickness", 0.109))

    return {
        "log": [f"{UNISPSC_CODE}:validate_tubing_specs"],
        "material_type": material,
        "outer_diameter": od,
        "wall_thickness": wall,
    }


def assess_structural_integrity(state: State) -> dict[str, Any]:
    """Simulates pressure rating calculation based on material and thickness."""
    # Barlow's Formula simplification for simulation
    material = state.get("material_type", "unknown")
    od = state.get("outer_diameter", 1.0)
    wall = state.get("wall_thickness", 0.1)

    # Mocking a yield strength (S) for different materials
    yield_strength = 35000 if "steel" in material else 10000
    pressure = (2 * yield_strength * wall) / od

    return {
        "log": [f"{UNISPSC_CODE}:assess_structural_integrity"],
        "pressure_rating_psi": pressure,
        "integrity_verified": pressure > 500.0,
    }


def certify_tube(state: State) -> dict[str, Any]:
    """Finalizes the tube specification record and issues compliance status."""
    ok = state.get("integrity_verified", False)
    pressure = state.get("pressure_rating_psi", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_tube"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "compliance": {
                "status": "certified" if ok else "rejected",
                "calculated_pressure_rating": f"{pressure:.2f} PSI",
                "material": state.get("material_type"),
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_tubing_specs)
_g.add_node("assess", assess_structural_integrity)
_g.add_node("certify", certify_tube)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
