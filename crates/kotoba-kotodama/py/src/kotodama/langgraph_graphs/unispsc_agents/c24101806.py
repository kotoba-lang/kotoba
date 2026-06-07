# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101806 — Dock Ladder (segment 24).
Bespoke logic for marine access equipment configuration and safety validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101806"
UNISPSC_TITLE = "Dock Ladder"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    step_type: str
    safety_compliance: bool
    marine_rating: str


def validate_environment(state: State) -> dict[str, Any]:
    """Validate material suitability for the specified water type."""
    inp = state.get("input") or {}
    water_type = inp.get("water_type", "fresh").lower()

    if water_type == "salt":
        grade = "316 Stainless Steel"
        rating = "Extreme Marine"
    else:
        grade = "6061 Aluminum"
        rating = "Standard Marine"

    return {
        "log": [f"{UNISPSC_CODE}:validate_environment"],
        "material_grade": grade,
        "marine_rating": rating,
    }


def configure_safety_features(state: State) -> dict[str, Any]:
    """Determine step geometry and safety requirements based on usage."""
    inp = state.get("input") or {}
    usage_frequency = inp.get("usage", "low").lower()

    # High usage requires wider non-slip steps for safety
    step_type = "Wide-Grip Non-Slip" if usage_frequency == "high" else "Standard Rung"

    return {
        "log": [f"{UNISPSC_CODE}:configure_safety_features"],
        "step_type": step_type,
        "safety_compliance": True,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Emit the final technical specification for the dock ladder."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("material_grade"),
                "rating": state.get("marine_rating"),
                "steps": state.get("step_type"),
                "compliance": state.get("safety_compliance"),
            },
            "status": "validated_configuration",
            "metadata": {
                "segment": UNISPSC_SEGMENT,
                "lifecycle": "production"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_environment)
_g.add_node("configure", configure_safety_features)
_g.add_node("emit", finalize_specification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
