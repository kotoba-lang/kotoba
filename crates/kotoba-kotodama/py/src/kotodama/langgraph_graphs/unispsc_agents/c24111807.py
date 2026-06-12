# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111807 — Tank.
Bespoke logic for industrial storage tank specification and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111807"
UNISPSC_TITLE = "Tank"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Tank
    capacity_liters: float
    material_grade: str
    pressure_max_psi: float
    integrity_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates tank capacity and material constraints from input."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 5000.0))
    material = str(inp.get("material", "AISI 304 Stainless Steel"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "capacity_liters": capacity,
        "material_grade": material,
    }


def assess_structural_integrity(state: State) -> dict[str, Any]:
    """Determines max pressure rating based on material and capacity."""
    material = state.get("material_grade", "")
    capacity = state.get("capacity_liters", 0.0)

    # Simple simulation: stainless handles more pressure than standard alloys
    base_pressure = 150.0
    if "Stainless" in material:
        base_pressure += 350.0

    # Larger tanks have lower pressure limits for standard wall thickness
    # in this simplified model.
    pressure_rating = base_pressure - (capacity / 1000.0)

    return {
        "log": [f"{UNISPSC_CODE}:assess_structural_integrity"],
        "pressure_max_psi": max(pressure_rating, 15.0),
        "integrity_verified": capacity > 0 and len(material) > 0,
    }


def finalize_tank_asset(state: State) -> dict[str, Any]:
    """Emits the final tank configuration and compliance status."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_tank_asset"],
        "result": {
            "asset_type": UNISPSC_TITLE,
            "code": UNISPSC_CODE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "capacity_liters": state.get("capacity_liters"),
                "material": state.get("material_grade"),
                "max_operating_pressure_psi": state.get("pressure_max_psi"),
            },
            "status": "APPROVED" if state.get("integrity_verified") else "PENDING_REVIEW",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_structural_integrity", assess_structural_integrity)
_g.add_node("finalize_tank_asset", finalize_tank_asset)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_structural_integrity")
_g.add_edge("assess_structural_integrity", "finalize_tank_asset")
_g.add_edge("finalize_tank_asset", END)

graph = _g.compile()
