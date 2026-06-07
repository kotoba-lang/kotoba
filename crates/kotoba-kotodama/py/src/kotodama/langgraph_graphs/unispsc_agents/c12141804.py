# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141804"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141804"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    substrate_type: str
    active_component_purity: float
    surface_area_m2g: float
    reaction_threshold_c: int
    is_stable: bool

def validate_composition(state: State) -> dict[str, Any]:
    """Validates the chemical composition and precursor purity requirements."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.995)
    return {
        "log": [f"{UNISPSC_CODE}:validate_composition"],
        "active_component_purity": purity,
        "substrate_type": inp.get("substrate", "Zeolite"),
        "is_stable": purity > 0.99,
    }

def perform_surface_analysis(state: State) -> dict[str, Any]:
    """Simulates characterization of surface area and activation energy."""
    return {
        "log": [f"{UNISPSC_CODE}:perform_surface_analysis"],
        "surface_area_m2g": 240.5,
        "reaction_threshold_c": 350,
    }

def certify_catalyst(state: State) -> dict[str, Any]:
    """Generates final compliance result for the catalyst batch."""
    stable = state.get("is_stable", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_catalyst"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "QUALIFIED" if stable else "FAILED",
            "metrics": {
                "surface_area": state.get("surface_area_m2g"),
                "threshold": state.get("reaction_threshold_c"),
                "purity": state.get("active_component_purity"),
            },
            "ok": stable,
        },
    }

_g = StateGraph(State)
_g.add_node("validate_composition", validate_composition)
_g.add_node("perform_surface_analysis", perform_surface_analysis)
_g.add_node("certify_catalyst", certify_catalyst)

_g.add_edge(START, "validate_composition")
_g.add_edge("validate_composition", "perform_surface_analysis")
_g.add_edge("perform_surface_analysis", "certify_catalyst")
_g.add_edge("certify_catalyst", END)

graph = _g.compile()
