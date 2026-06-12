# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121810"
UNISPSC_TITLE = "Abrasive"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121810"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Abrasive materials
    material_composition: str
    grit_rating: int
    application_type: str
    safety_specs_verified: bool


def identify_material(state: State) -> dict[str, Any]:
    """Analyzes the material composition and base grit density."""
    inp = state.get("input") or {}
    composition = inp.get("material", "aluminum_oxide")
    grit = inp.get("grit", 120)
    return {
        "log": [f"{UNISPSC_CODE}:identify_material -> {composition} (grit {grit})"],
        "material_composition": composition,
        "grit_rating": grit,
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Ensures the abrasive material meets industrial safety and toxicity standards."""
    composition = state.get("material_composition", "unknown")
    # Simulation: aluminum oxide and ceramic are generally pre-cleared for safety
    is_safe = composition.lower() in ["aluminum_oxide", "ceramic", "garnet"]
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards -> safe={is_safe}"],
        "safety_specs_verified": is_safe,
    }


def determine_application(state: State) -> dict[str, Any]:
    """Determines the optimal use case based on grit rating and safety status."""
    grit = state.get("grit_rating", 0)
    safe = state.get("safety_specs_verified", False)

    if grit < 100:
        app = "Stock Removal"
    elif grit < 240:
        app = "Surface Preparation"
    else:
        app = "Fine Finishing"

    return {
        "log": [f"{UNISPSC_CODE}:determine_application -> {app}"],
        "application_type": app,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if safe else "inspection_required",
            "specifications": {
                "material": state.get("material_composition"),
                "grit": grit,
                "primary_use": app,
            }
        },
    }


_g = StateGraph(State)
_g.add_node("identify_material", identify_material)
_g.add_node("verify_safety_standards", verify_safety_standards)
_g.add_node("determine_application", determine_application)

_g.add_edge(START, "identify_material")
_g.add_edge("identify_material", "verify_safety_standards")
_g.add_edge("verify_safety_standards", "determine_application")
_g.add_edge("determine_application", END)

graph = _g.compile()
