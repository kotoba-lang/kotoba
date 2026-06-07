# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151510 — Metallurgical (segment 11).

Bespoke graph logic for metallurgical ore analysis and extraction yield estimation.
This agent processes raw mineral data to determine purity and potential yield.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151510"
UNISPSC_TITLE = "Metallurgical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Metallurgical
    ore_grade: float
    impurity_levels: dict[str, float]
    extraction_method: str
    refined_yield: float
    is_certified: bool


def inspect_ore(state: State) -> dict[str, Any]:
    """Inspects the incoming ore sample for grade and impurity levels."""
    inp = state.get("input") or {}
    grade = float(inp.get("grade", 0.0))
    impurities = inp.get("impurities", {"silica": 0.05, "sulfur": 0.01})

    return {
        "log": [f"{UNISPSC_CODE}:inspect_ore -> grade={grade}"],
        "ore_grade": grade,
        "impurity_levels": impurities,
        "extraction_method": inp.get("method", "pyrometallurgy"),
    }


def calculate_extraction(state: State) -> dict[str, Any]:
    """Estimates the refined yield based on grade and extraction method."""
    grade = state.get("ore_grade", 0.0)
    method = state.get("extraction_method", "unknown")

    # Simple logic: hydrometallurgy has higher recovery for low grade,
    # pyrometallurgy is faster for high grade.
    efficiency = 0.92 if method == "hydrometallurgy" else 0.88
    yield_val = grade * efficiency

    return {
        "log": [f"{UNISPSC_CODE}:calculate_extraction -> method={method}, yield={yield_val:.4f}"],
        "refined_yield": yield_val,
        "is_certified": yield_val > 0.1,
    }


def certify_metallurgy(state: State) -> dict[str, Any]:
    """Generates the final metallurgical analysis certificate."""
    is_ok = state.get("is_certified", False)
    yield_val = state.get("refined_yield", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_metallurgy -> ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "analysis": {
                "refined_yield_pct": yield_val * 100,
                "status": "APPROVED" if is_ok else "REJECTED",
                "segment": UNISPSC_SEGMENT,
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_ore", inspect_ore)
_g.add_node("calculate_extraction", calculate_extraction)
_g.add_node("certify_metallurgy", certify_metallurgy)

_g.add_edge(START, "inspect_ore")
_g.add_edge("inspect_ore", "calculate_extraction")
_g.add_edge("calculate_extraction", "certify_metallurgy")
_g.add_edge("certify_metallurgy", END)

graph = _g.compile()
