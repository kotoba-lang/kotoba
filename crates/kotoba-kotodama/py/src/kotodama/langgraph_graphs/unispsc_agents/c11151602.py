# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151602 — Material.
Bespoke graph logic for industrial material processing and quality control.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151602"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Material" (Segment 11: Earth/Mineral/Stone)
    material_category: str
    density_spec: float
    is_hazardous: bool
    quality_score: int


def classify(state: State) -> dict[str, Any]:
    """Identify and classify the raw material input."""
    inp = state.get("input") or {}
    category = inp.get("category", "raw_ore")
    is_haz = inp.get("hazmat", False)
    return {
        "log": [f"{UNISPSC_CODE}:classify:{category}"],
        "material_category": category,
        "is_hazardous": is_haz,
    }


def analyze(state: State) -> dict[str, Any]:
    """Perform structural and density analysis on the material."""
    inp = state.get("input") or {}
    density = float(inp.get("density", 2.7))
    # Synthetic quality scoring logic based on density and safety
    score = 100 if density > 2.5 else 75
    if state.get("is_hazardous"):
        score -= 20
    return {
        "log": [f"{UNISPSC_CODE}:analyze:density={density}"],
        "density_spec": density,
        "quality_score": score,
    }


def certify(state: State) -> dict[str, Any]:
    """Generate final certification and output result."""
    score = state.get("quality_score", 0)
    passed = score >= 70
    return {
        "log": [f"{UNISPSC_CODE}:certify:score={score}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality_certified": passed,
            "category": state.get("material_category"),
            "final_score": score,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("classify", classify)
_g.add_node("analyze", analyze)
_g.add_node("certify", certify)

_g.add_edge(START, "classify")
_g.add_edge("classify", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
