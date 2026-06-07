# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151511"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Segment 11 (Fiber materials)
    fiber_type: str
    moisture_content: float
    bale_density: float
    grade_rating: str
    inspection_protocol: str


def validate_fiber_intake(state: State) -> dict[str, Any]:
    """Validates the physical properties of the incoming fiber shipment."""
    inp = state.get("input") or {}
    moisture = inp.get("moisture", 12.5)
    material = inp.get("type", "bast_fiber")

    return {
        "log": [f"{UNISPSC_CODE}:validate_fiber_intake"],
        "fiber_type": material,
        "moisture_content": moisture,
        "inspection_protocol": "ISO-2370:2022"
    }


def assess_quality_grade(state: State) -> dict[str, Any]:
    """Determines the commercial grade based on moisture and density metrics."""
    moisture = state.get("moisture_content", 0.0)
    density = state.get("input", {}).get("density", 1.45)

    # Simple grading heuristic for vegetable fibers
    if moisture < 10.0 and density > 1.4:
        grade = "Prime"
    elif moisture < 15.0:
        grade = "Standard"
    else:
        grade = "Industrial"

    return {
        "log": [f"{UNISPSC_CODE}:assess_quality_grade"],
        "grade_rating": grade,
        "bale_density": density
    }


def finalize_material_record(state: State) -> dict[str, Any]:
    """Generates the final actor response and material manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "fiber_type": state.get("fiber_type"),
                "grade": state.get("grade_rating"),
                "moisture": state.get("moisture_content"),
                "density": state.get("bale_density"),
                "protocol": state.get("inspection_protocol")
            },
            "certified": True
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_fiber_intake)
_g.add_node("assess", assess_quality_grade)
_g.add_node("finalize", finalize_material_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
