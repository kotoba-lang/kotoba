# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141705"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for industrial Catalysts
    chemical_composition: str
    surface_area_m2g: float
    porosity_ratio: float
    thermal_stability_k: int
    is_poisoned: bool


def verify_composition(state: State) -> dict[str, Any]:
    """Verify the chemical composition and initial specifications of the catalyst."""
    inp = state.get("input") or {}
    composition = inp.get("composition", "platinum-alumina")
    thermal_k = inp.get("temp_limit", 800)

    return {
        "log": [f"{UNISPSC_CODE}:verify_composition"],
        "chemical_composition": composition,
        "thermal_stability_k": thermal_k,
        "is_poisoned": False
    }


def analyze_structural_properties(state: State) -> dict[str, Any]:
    """Calculate effective surface area and porosity for reaction efficiency."""
    # Simulated analysis based on composition provided in previous node
    composition = state.get("chemical_composition", "")
    if "platinum" in composition:
        sa = 250.5
        pr = 0.65
    else:
        sa = 120.0
        pr = 0.42

    return {
        "log": [f"{UNISPSC_CODE}:analyze_structural_properties"],
        "surface_area_m2g": sa,
        "porosity_ratio": pr
    }


def assess_reactivity(state: State) -> dict[str, Any]:
    """Final check of reactivity metrics and emit production readiness result."""
    sa = state.get("surface_area_m2g", 0.0)
    is_poisoned = state.get("is_poisoned", False)

    reactivity_score = sa * 0.8 if not is_poisoned else 0.0
    ready = reactivity_score > 100.0

    return {
        "log": [f"{UNISPSC_CODE}:assess_reactivity"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "reactivity_score": reactivity_score,
            "status": "APPROVED" if ready else "REJECTED",
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("verify_composition", verify_composition)
_g.add_node("analyze_structural_properties", analyze_structural_properties)
_g.add_node("assess_reactivity", assess_reactivity)

_g.add_edge(START, "verify_composition")
_g.add_edge("verify_composition", "analyze_structural_properties")
_g.add_edge("analyze_structural_properties", "assess_reactivity")
_g.add_edge("assess_reactivity", END)

graph = _g.compile()
