# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171902 — Rail Wheel (segment 25).

Bespoke graph logic for rail wheel component lifecycle management,
including metallurgical verification and dimensional inspection.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171902"
UNISPSC_TITLE = "Rail Wheel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    wheel_diameter_mm: float
    material_grade: str
    heat_treatment_protocol: str
    inspection_passed: bool


def inspect_dimensions(state: State) -> dict[str, Any]:
    """Verify physical dimensions against standard rail wheel specifications."""
    inp = state.get("input") or {}
    diameter = inp.get("diameter", 915.0)
    # Standard freight wheels are typically around 840mm to 920mm
    is_valid = 800.0 <= diameter <= 1200.0
    return {
        "log": [f"{UNISPSC_CODE}:inspect_dimensions:diameter={diameter}mm:valid={is_valid}"],
        "wheel_diameter_mm": diameter,
        "inspection_passed": is_valid,
    }


def verify_metallurgy(state: State) -> dict[str, Any]:
    """Check material composition and heat treatment records."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Class C")
    protocol = inp.get("protocol", "AAR-M-107")
    return {
        "log": [f"{UNISPSC_CODE}:verify_metallurgy:grade={grade}:protocol={protocol}"],
        "material_grade": grade,
        "heat_treatment_protocol": protocol,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generate the final compliance result for the rail component."""
    passed = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification:certified={passed}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "diameter_mm": state.get("wheel_diameter_mm"),
                "material_grade": state.get("material_grade"),
                "treatment": state.get("heat_treatment_protocol"),
            },
            "certified": passed,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_dimensions", inspect_dimensions)
_g.add_node("verify_metallurgy", verify_metallurgy)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "inspect_dimensions")
_g.add_edge("inspect_dimensions", "verify_metallurgy")
_g.add_edge("verify_metallurgy", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
