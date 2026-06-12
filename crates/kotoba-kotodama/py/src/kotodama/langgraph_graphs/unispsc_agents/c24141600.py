# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141600"
UNISPSC_TITLE = "Packing"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Packing
    specs_validated: bool
    packing_material: str
    gross_weight: float
    container_type: str
    is_fragile: bool


def validate_packing_requirements(state: State) -> dict[str, Any]:
    """Validates the input specifications for the packing task."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight_kg", 0.0))
    fragile = bool(inp.get("fragile", False))

    # Simple validation logic
    is_valid = weight > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_packing_requirements"],
        "specs_validated": is_valid,
        "gross_weight": weight,
        "is_fragile": fragile
    }


def select_containment_strategy(state: State) -> dict[str, Any]:
    """Determines the appropriate packing material and container based on state."""
    weight = state.get("gross_weight", 0.0)
    fragile = state.get("is_fragile", False)

    if fragile:
        material = "Multi-layer Bubble Wrap & Foam"
        container = "Cushioned Reinforced Carton"
    elif weight > 50.0:
        material = "Industrial Strapping & Pallet Wrap"
        container = "Heavy-Duty Wooden Crate"
    else:
        material = "Recycled Kraft Paper"
        container = "Standard Corrugated Box"

    return {
        "log": [f"{UNISPSC_CODE}:select_containment_strategy"],
        "packing_material": material,
        "container_type": container
    }


def emit_packing_slip(state: State) -> dict[str, Any]:
    """Finalizes the packing process and emits the result manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_packing_slip"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "manifest": {
                "container": state.get("container_type"),
                "material": state.get("packing_material"),
                "weight_verified": state.get("gross_weight"),
                "fragile_status": state.get("is_fragile")
            },
            "status": "Packing Complete",
            "ok": state.get("specs_validated", False)
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_packing_requirements)
_g.add_node("strategy", select_containment_strategy)
_g.add_node("emit", emit_packing_slip)

_g.add_edge(START, "validate")
_g.add_edge("validate", "strategy")
_g.add_edge("strategy", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
