# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102028 — Mineral Oil (segment 13).

Bespoke agent implementation for Mineral Oil lifecycle management.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102028"
UNISPSC_TITLE = "Mineral Oil"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102028"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    grade: str
    viscosity_cst: float
    is_saturated: bool
    batch_safety_verified: bool


def analyze_feedstock(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    grade = inp.get("target_grade", "technical")
    viscosity = float(inp.get("target_viscosity", 15.0))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_feedstock"],
        "grade": grade,
        "viscosity_cst": viscosity,
        "is_saturated": False,
        "batch_safety_verified": False
    }


def refine_hydrogenation(state: State) -> dict[str, Any]:
    # Simulate the saturation process for mineral oil purity
    grade = state.get("grade")
    # Food and medicinal grades require full saturation (removal of aromatics)
    saturation_level = True if grade in ["food", "medicinal"] else False

    return {
        "log": [f"{UNISPSC_CODE}:refine_hydrogenation"],
        "is_saturated": saturation_level,
        "batch_safety_verified": saturation_level if grade != "technical" else True
    }


def finalize_and_certify(state: State) -> dict[str, Any]:
    is_safe = state.get("batch_safety_verified", False)
    grade = state.get("grade", "technical")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_and_certify"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_grade": grade,
            "viscosity_cst": state.get("viscosity_cst"),
            "safety_pass": is_safe,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_feedstock", analyze_feedstock)
_g.add_node("refine_hydrogenation", refine_hydrogenation)
_g.add_node("finalize_and_certify", finalize_and_certify)

_g.add_edge(START, "analyze_feedstock")
_g.add_edge("analyze_feedstock", "refine_hydrogenation")
_g.add_edge("refine_hydrogenation", "finalize_and_certify")
_g.add_edge("finalize_and_certify", END)

graph = _g.compile()
