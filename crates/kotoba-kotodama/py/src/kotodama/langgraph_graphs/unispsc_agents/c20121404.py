# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121404 — Bearing (segment 20).

Bespoke graph logic for mechanical bearing specifications, load capacity
validation, and technical compliance assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121404"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121404"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bearing components
    bearing_type: str           # e.g., Ball, Roller, Needle, Tapered
    material_grade: str         # e.g., AISI 52100, Stainless Steel
    load_rating_kn: float       # Dynamic load rating in kiloNewtons
    dimensions_mm: dict[str, float]  # {'id': inner, 'od': outer, 'w': width}
    is_compliant: bool          # Engineering validation status


def inspect_spec(state: State) -> dict[str, Any]:
    """Inspects the input engineering specifications for the bearing component."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    bearing_type = specs.get("type", "standard_ball")
    material = specs.get("material", "AISI 52100")
    dims = specs.get("dimensions", {"id": 0.0, "od": 0.0, "w": 0.0})
    load = specs.get("load_rating", 0.0)

    # Basic structural check
    has_dimensions = dims.get("id", 0) > 0 and dims.get("od", 0) > dims.get("id", 0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "bearing_type": bearing_type,
        "material_grade": material,
        "dimensions_mm": dims,
        "load_rating_kn": load,
        "is_compliant": has_dimensions and load > 0
    }


def validate_load_capacity(state: State) -> dict[str, Any]:
    """Validates the bearing's load capacity against application requirements."""
    load_kn = state.get("load_rating_kn", 0.0)
    material = state.get("material_grade", "")

    # Mock engineering logic: certain materials require higher minimum ratings
    is_valid = state.get("is_compliant", False)
    if "Stainless" in material and load_kn < 0.2:
        is_valid = False
    elif load_kn <= 0:
        is_valid = False

    return {
        "log": [f"{UNISPSC_CODE}:validate_load_capacity"],
        "is_compliant": is_valid
    }


def certify_component(state: State) -> dict[str, Any]:
    """Generates the final certification record for the bearing unit."""
    is_ok = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": {
                "type": state.get("bearing_type"),
                "material": state.get("material_grade"),
                "load_rating": f"{state.get('load_rating_kn')} kN",
                "validated_dimensions": state.get("dimensions_mm")
            },
            "status": "CERTIFIED" if is_ok else "NON_COMPLIANT",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_spec", inspect_spec)
_g.add_node("validate_load_capacity", validate_load_capacity)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "validate_load_capacity")
_g.add_edge("validate_load_capacity", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
