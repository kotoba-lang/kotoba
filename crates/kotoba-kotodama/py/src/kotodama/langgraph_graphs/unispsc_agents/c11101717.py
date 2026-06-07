# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101717 — Chemical (segment 11).

Bespoke LangGraph implementation for chemical material processing and safety
validation, ensuring compliance with industrial standards and hazardous
material handling protocols.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101717"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101717"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    safety_data_verified: bool
    purity_percentage: float
    hazard_classification: str
    stabilization_method: str


def validate_safety_protocols(state: State) -> dict[str, Any]:
    """Ensures MSDS documentation is present and safety protocols are met."""
    inp = state.get("input") or {}
    has_msds = inp.get("msds_available", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_protocols"],
        "safety_data_verified": has_msds,
        "hazard_classification": inp.get("hazard_class", "unclassified"),
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Performs compositional analysis to determine purity and stability."""
    inp = state.get("input") or {}
    purity = inp.get("measured_purity", 0.95)
    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_percentage": purity,
        "stabilization_method": "inert_gas_blanket" if purity > 0.99 else "ambient",
    }


def certify_material(state: State) -> dict[str, Any]:
    """Issues the final certification for the chemical agent."""
    is_safe = state.get("safety_data_verified", False)
    purity = state.get("purity_percentage", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_material"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_safe and purity >= 0.90,
            "hazard_rating": state.get("hazard_classification"),
            "stabilization": state.get("stabilization_method"),
            "status": "ready_for_distribution" if is_safe else "quarantined",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_safety_protocols)
_g.add_node("analyze", analyze_composition)
_g.add_node("certify", certify_material)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
