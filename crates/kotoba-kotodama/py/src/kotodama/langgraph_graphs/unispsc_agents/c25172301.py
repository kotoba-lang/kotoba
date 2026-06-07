# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172301 — Glass.
Bespoke logic for glass specification validation and quality assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172301"
UNISPSC_TITLE = "Glass"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Glass
    glass_type: str
    dimensions_mm: dict[str, float]
    quality_grade: str
    safety_compliant: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the glass component."""
    inp = state.get("input") or {}
    g_type = inp.get("type", "standard-float")
    dims = inp.get("dimensions", {"w": 0.0, "h": 0.0, "t": 0.0})

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "glass_type": g_type,
        "dimensions_mm": dims,
    }


def assess_quality(state: State) -> dict[str, Any]:
    """Determines safety compliance and quality grade based on material properties."""
    dims = state.get("dimensions_mm", {})
    thickness = dims.get("t", 0.0)
    g_type = state.get("glass_type", "")

    # Heuristic: Thicker glass or specialized types meet safety thresholds
    is_safe = thickness >= 6.0 or any(kw in g_type.lower() for kw in ["tempered", "laminated", "safety"])
    grade = "A+" if (is_safe and thickness > 10.0) else ("A" if is_safe else "B")

    return {
        "log": [f"{UNISPSC_CODE}:assess_quality"],
        "safety_compliant": is_safe,
        "quality_grade": grade,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Sets the final result with the generated glass certification metadata."""
    is_safe = state.get("safety_compliant", False)
    grade = state.get("quality_grade", "N/A")
    g_type = state.get("glass_type", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": {
                "type": g_type,
                "grade": grade,
                "safety_compliant": is_safe,
            },
            "status": "certified" if is_safe else "pending_review",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_quality", assess_quality)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_quality")
_g.add_edge("assess_quality", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
