# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162128 — Si C (Silicon Carbide).

Bespoke graph for industrial Silicon Carbide mineral processing and grade
assessment. This agent validates material specifications, characterizes
thermal and abrasive properties, and generates compliant batch results.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162128"
UNISPSC_TITLE = "Si C"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162128"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_pct: float
    mesh_size: int
    grade_category: str
    thermal_stability_verified: bool


def inspect_composition(state: State) -> dict[str, Any]:
    """Inspects the raw Silicon Carbide input for purity and particle size."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    mesh = int(inp.get("mesh", 0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "purity_pct": purity,
        "mesh_size": mesh,
    }


def classify_grade(state: State) -> dict[str, Any]:
    """Classifies the material into abrasive, refractory, or metallurgical grades."""
    purity = state.get("purity_pct", 0.0)

    if purity >= 99.5:
        category = "Semiconductor/Refractory"
    elif purity >= 90.0:
        category = "Abrasive"
    else:
        category = "Metallurgical"

    return {
        "log": [f"{UNISPSC_CODE}:classify_grade"],
        "grade_category": category,
        "thermal_stability_verified": purity > 95.0,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the batch certification record for the Si C material."""
    category = state.get("grade_category", "Unknown")
    is_valid = state.get("purity_pct", 0.0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "grade": category,
            "mesh": state.get("mesh_size"),
            "thermal_stable": state.get("thermal_stability_verified"),
            "certified": is_valid,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_composition", inspect_composition)
_g.add_node("classify_grade", classify_grade)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "classify_grade")
_g.add_edge("classify_grade", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
