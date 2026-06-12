# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101742 — Fuel (segment 26).
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101742"
UNISPSC_TITLE = "Fuel"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101742"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Fuel monitoring
    fuel_category: str
    octane_rating: int
    sulfur_content_ppm: float
    volatility_index: float
    safety_validated: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Node to validate the base fuel properties from input."""
    inp = state.get("input") or {}
    category = str(inp.get("category", "unleaded_gasoline"))
    octane = int(inp.get("octane", 87))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "fuel_category": category,
        "octane_rating": octane,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Node to check sulfur and volatility compliance."""
    inp = state.get("input") or {}
    sulfur = float(inp.get("sulfur", 10.0))
    volatility = float(inp.get("volatility", 1.2))

    # Simple logic for safety validation
    is_safe = sulfur <= 15.0 and volatility < 2.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "sulfur_content_ppm": sulfur,
        "volatility_index": volatility,
        "safety_validated": is_safe,
    }


def finalize_inventory_record(state: State) -> dict[str, Any]:
    """Node to emit the final certification for the fuel batch."""
    is_safe = state.get("safety_validated", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_safe else "REJECTED",
            "spec_summary": {
                "category": state.get("fuel_category"),
                "octane": state.get("octane_rating"),
                "sulfur_ppm": state.get("sulfur_content_ppm")
            },
            "verified": True
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("analyze", analyze_composition)
_g.add_node("finalize", finalize_inventory_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
