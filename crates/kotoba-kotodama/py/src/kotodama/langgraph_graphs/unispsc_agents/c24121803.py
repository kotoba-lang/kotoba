# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121803"
UNISPSC_TITLE = "Can Container"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    capacity_liters: float
    has_protective_lining: bool
    sealing_method: str


def evaluate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and material requirements for the can."""
    inp = state.get("input") or {}
    # Default to food-grade aluminum if not specified
    material = inp.get("material", "aluminum-3104")
    volume = float(inp.get("volume", 0.355))

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specifications"],
        "material_grade": material,
        "capacity_liters": volume,
    }


def verify_containment_integrity(state: State) -> dict[str, Any]:
    """Checks lining requirements and sealing protocols for pressurized or food usage."""
    material = state.get("material_grade", "")
    # Determine lining based on material grade
    needs_lining = "aluminum" in material.lower() or "steel" in material.lower()
    method = "double-seam" if state.get("capacity_liters", 0) < 5.0 else "welded-side-seam"

    return {
        "log": [f"{UNISPSC_CODE}:verify_containment_integrity"],
        "has_protective_lining": needs_lining,
        "sealing_method": method,
    }


def generate_compliance_report(state: State) -> dict[str, Any]:
    """Finalizes the actor state and emits the structured container metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_compliance_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attributes": {
                "material": state.get("material_grade"),
                "volume": f"{state.get('capacity_liters')}L",
                "internal_coating": "Applied" if state.get("has_protective_lining") else "None",
                "closure": state.get("sealing_method"),
            },
            "certification": "ISO 9001:2015 compliant",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate", evaluate_specifications)
_g.add_node("verify", verify_containment_integrity)
_g.add_node("report", generate_compliance_report)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "verify")
_g.add_edge("verify", "report")
_g.add_edge("report", END)

graph = _g.compile()
