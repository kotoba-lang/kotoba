# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141200 — Mining Parts (segment 20).

Bespoke graph logic for managing mining equipment components, durability
assessments, and machinery compatibility checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141200"
UNISPSC_TITLE = "Mining Parts"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141200"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Mining Parts
    part_id: str
    material_grade: str
    wear_coefficient: float
    compatibility_matrix: list[str]
    is_hardened: bool


def validate_part_data(state: State) -> dict[str, Any]:
    """Validates the incoming mining part specifications."""
    inp = state.get("input") or {}
    part_id = inp.get("part_id", "UNKNOWN-PART")
    material = inp.get("material", "standard_alloy")

    return {
        "log": [f"{UNISPSC_CODE}:validate_part_data"],
        "part_id": part_id,
        "material_grade": material,
        "is_hardened": "hardened" in material.lower() or "tungsten" in material.lower()
    }


def assess_durability(state: State) -> dict[str, Any]:
    """Calculates the wear coefficient based on material grade and hardening."""
    base_coefficient = 0.85
    if state.get("is_hardened"):
        base_coefficient = 0.98

    # Simulate material-specific logic
    grade = state.get("material_grade", "")
    if "carbide" in grade.lower():
        base_coefficient += 0.05

    return {
        "log": [f"{UNISPSC_CODE}:assess_durability"],
        "wear_coefficient": round(base_coefficient, 3)
    }


def verify_machinery_fit(state: State) -> dict[str, Any]:
    """Determines compatibility with common mining machinery types."""
    # Mock compatibility check
    fits = ["Excavator-7000", "Drill-Rig-X1"]
    if state.get("wear_coefficient", 0) > 0.95:
        fits.append("Heavy-Duty-Crusher")

    return {
        "log": [f"{UNISPSC_CODE}:verify_machinery_fit"],
        "compatibility_matrix": fits,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "part_id": state.get("part_id"),
            "wear_rating": state.get("wear_coefficient"),
            "compatible_equipment": fits,
            "did": UNISPSC_DID,
            "status": "certified"
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_part_data)
_g.add_node("assess", assess_durability)
_g.add_node("verify", verify_machinery_fit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
