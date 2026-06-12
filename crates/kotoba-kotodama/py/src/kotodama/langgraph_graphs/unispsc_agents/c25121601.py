# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121601 — Rail.
Bespoke graph logic for marine or vehicle rail components (Segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121601"
UNISPSC_TITLE = "Rail"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Rail components
    material_grade: str
    dimensions_mm: dict[str, float]
    mounting_config: str
    safety_compliance: bool
    structural_integrity_score: float


def validate_spec(state: State) -> dict[str, Any]:
    """Validates material and dimensions for the rail component."""
    inp = state.get("input") or {}
    material = inp.get("material", "316_stainless")
    dims = inp.get("dimensions", {"length": 1500, "diameter": 25})

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec: {material}"],
        "material_grade": material,
        "dimensions_mm": dims,
        "safety_compliance": material.startswith("316") or material == "aluminum_marine"
    }


def analyze_structure(state: State) -> dict[str, Any]:
    """Calculates structural integrity based on mounting and dimensions."""
    dims = state.get("dimensions_mm", {})
    length = dims.get("length", 1000)
    # Simple mock logic: longer rails without enough supports have lower scores
    score = 1.0 if length < 2000 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:analyze_structure: score={score}"],
        "structural_integrity_score": score,
        "mounting_config": state.get("input", {}).get("mounting", "top_mount")
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final certification and manifest entry."""
    is_ok = state.get("safety_compliance", False) and state.get("structural_integrity_score", 0) > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification: pass={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_ok else "REJECTED",
            "metadata": {
                "material": state.get("material_grade"),
                "mounting": state.get("mounting_config"),
                "integrity": state.get("structural_integrity_score")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_spec)
_g.add_node("analyze", analyze_structure)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
