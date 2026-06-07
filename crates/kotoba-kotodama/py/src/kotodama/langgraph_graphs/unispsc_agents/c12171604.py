# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12171604 — Material (segment 12).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12171604"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12171604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_composition: str
    safety_rating: int
    is_hazardous: bool
    inventory_tracking_id: str


def validate_material(state: State) -> dict[str, Any]:
    """Validates the input material specifications and checks for hazards."""
    inp = state.get("input") or {}
    composition = inp.get("composition", "general_substrate")
    hazardous = any(x in composition.lower() for x in ["acid", "toxic", "flammable", "reactive"])

    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "material_composition": composition,
        "is_hazardous": hazardous,
    }


def assess_properties(state: State) -> dict[str, Any]:
    """Assesses material properties and assigns safety metrics and tracking."""
    hazardous = state.get("is_hazardous", False)
    # Simple logic to determine a safety rating based on hazard status
    rating = 3 if hazardous else 9
    tracking_id = f"MAT-{UNISPSC_CODE}-{abs(hash(state.get('material_composition', ''))) % 10000:04d}"

    return {
        "log": [f"{UNISPSC_CODE}:assess_properties"],
        "safety_rating": rating,
        "inventory_tracking_id": tracking_id,
    }


def emit_manifest(state: State) -> dict[str, Any]:
    """Emits the final material manifest and verification status."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "tracking_id": state.get("inventory_tracking_id"),
                "composition": state.get("material_composition"),
                "safety_rating": state.get("safety_rating"),
                "hazardous": state.get("is_hazardous"),
            },
            "status": "verified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_material)
_g.add_node("assess", assess_properties)
_g.add_node("emit", emit_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
