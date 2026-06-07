# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12131603 — Lubricant (segment 12).

Bespoke graph logic for handling lubricant product specifications,
viscosity verification, and compatibility analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131603"
UNISPSC_TITLE = "Lubricant"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lubricant
    viscosity_grade: str
    base_oil_type: str
    temperature_range: tuple[float, float]
    compatibility_score: float
    spec_verified: bool


def verify_specifications(state: State) -> dict[str, Any]:
    """Extracts and verifies lubricant specifications from input."""
    inp = state.get("input") or {}
    viscosity = inp.get("viscosity", "ISO VG 46")
    base_oil = inp.get("base_oil", "Synthetic")

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications -> {viscosity}/{base_oil}"],
        "viscosity_grade": viscosity,
        "base_oil_type": base_oil,
        "spec_verified": True
    }


def evaluate_compatibility(state: State) -> dict[str, Any]:
    """Evaluates the lubricant's suitability for the requested temperature range."""
    inp = state.get("input") or {}
    target_range = inp.get("target_temp", (-20.0, 100.0))

    # Simulate a compatibility calculation based on base oil type
    score = 0.95 if state.get("base_oil_type") == "Synthetic" else 0.75

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_compatibility -> score {score}"],
        "temperature_range": target_range,
        "compatibility_score": score
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Compiles the final validation result for the lubricant agent."""
    is_ok = state.get("spec_verified", False) and state.get("compatibility_score", 0) > 0.5

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record -> ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "viscosity": state.get("viscosity_grade"),
            "base_oil": state.get("base_oil_type"),
            "score": state.get("compatibility_score"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specifications", verify_specifications)
_g.add_node("evaluate_compatibility", evaluate_compatibility)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "verify_specifications")
_g.add_edge("verify_specifications", "evaluate_compatibility")
_g.add_edge("evaluate_compatibility", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
