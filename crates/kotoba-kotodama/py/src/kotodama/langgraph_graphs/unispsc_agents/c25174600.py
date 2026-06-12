# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174600 — Seat Spec (segment 25).

Bespoke LangGraph logic for managing transportation seating specifications,
ensuring compliance with material safety and structural requirements.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174600"
UNISPSC_TITLE = "Seat Spec"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Seat Spec
    material_safety_verified: bool
    structural_integrity_score: float
    upholstery_type: str
    ergonomic_compliance: bool


def analyze_spec(state: State) -> dict[str, Any]:
    """Analyzes the input specifications for material and ergonomic data."""
    inp = state.get("input") or {}
    upholstery = inp.get("upholstery", "standard-synthetic")
    features = inp.get("features", [])

    return {
        "log": [f"{UNISPSC_CODE}:analyze_spec"],
        "upholstery_type": upholstery,
        "ergonomic_compliance": "lumbar_support" in features or "adjustable_headrest" in features,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Verifies the fire resistance and structural capacity of the seat spec."""
    inp = state.get("input") or {}
    weight_rating = inp.get("max_load_kg", 0)
    fire_rating = inp.get("fire_resistance", "None")

    # Safety logic: requires a weight rating and some fire resistance level
    is_safe = weight_rating >= 100 and fire_rating != "None"

    # Calculate a mock integrity score based on weight capacity
    score = min(1.0, weight_rating / 200.0) if weight_rating > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "material_safety_verified": is_safe,
        "structural_integrity_score": score,
    }


def finalize_spec(state: State) -> dict[str, Any]:
    """Finalizes the seat specification and prepares the actor result."""
    safe = state.get("material_safety_verified", False)
    score = state.get("structural_integrity_score", 0.0)
    ergonomic = state.get("ergonomic_compliance", False)

    # A passing spec must be safe and have a decent structural score
    spec_passed = safe and score > 0.6

    return {
        "log": [f"{UNISPSC_CODE}:finalize_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "upholstery": state.get("upholstery_type"),
            "ergonomic_certified": ergonomic,
            "structural_score": round(score, 2),
            "compliance_status": "APPROVED" if spec_passed else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_spec", analyze_spec)
_g.add_node("verify_safety", verify_safety)
_g.add_node("finalize_spec", finalize_spec)

_g.add_edge(START, "analyze_spec")
_g.add_edge("analyze_spec", "verify_safety")
_g.add_edge("verify_safety", "finalize_spec")
_g.add_edge("finalize_spec", END)

graph = _g.compile()
