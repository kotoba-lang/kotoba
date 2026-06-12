# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141605 — Packing Material (segment 24).

Bespoke logic for assessing packing material specifications, durability,
and recycling compatibility.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141605"
UNISPSC_TITLE = "Packing Material"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Packing Material
    material_type: str
    protection_rating: float
    recyclability_index: float
    safety_compliance: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects the input for material specifications and safety standards."""
    inp = state.get("input") or {}
    m_type = inp.get("material_type", "corrugated_cardboard")
    compliant = inp.get("iso_certified", True)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "material_type": m_type,
        "safety_compliance": compliant,
    }


def evaluate_performance(state: State) -> dict[str, Any]:
    """Evaluates the cushioning performance and environmental impact."""
    m_type = state.get("material_type", "unknown")

    # Default values for synthetic performance metrics
    rating = 0.5
    recycling = 1.0

    lower_type = m_type.lower()
    if "foam" in lower_type:
        rating = 0.95
        recycling = 0.15
    elif "bubble" in lower_type:
        rating = 0.85
        recycling = 0.35
    elif "paper" in lower_type or "cardboard" in lower_type:
        rating = 0.65
        recycling = 0.98

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_performance"],
        "protection_rating": rating,
        "recyclability_index": recycling,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Finalizes the packing material certification and metadata."""
    is_safe = state.get("safety_compliance", False)
    perf = state.get("protection_rating", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_safe and perf > 0.4,
            "metrics": {
                "protection": perf,
                "recyclability": state.get("recyclability_index"),
                "material": state.get("material_type")
            },
            "ok": True
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("evaluate_performance", evaluate_performance)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "evaluate_performance")
_g.add_edge("evaluate_performance", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
