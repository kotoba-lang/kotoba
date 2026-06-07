# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122312 — Robot Gear (segment 20).

Bespoke graph logic for industrial and robotic gear systems, handling
specification validation, tolerance calculations, and configuration output.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122312"
UNISPSC_TITLE = "Robot Gear"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122312"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Robot Gear
    gear_profile: str
    material_grade: str
    backlash_arcmin: float
    is_compliant: bool


def validate_profile(state: State) -> dict[str, Any]:
    """Validates the mechanical profile of the robot gear."""
    inp = state.get("input") or {}
    profile = inp.get("profile", "involute")
    grade = inp.get("material", "AISI_4140")
    return {
        "log": [f"{UNISPSC_CODE}:validate_profile"],
        "gear_profile": profile,
        "material_grade": grade,
    }


def calculate_precision(state: State) -> dict[str, Any]:
    """Calculates backlash and precision constraints for robotic motion."""
    inp = state.get("input") or {}
    # Robotic gears often require low backlash (< 3 arcmin)
    backlash = float(inp.get("requested_backlash", 5.0))
    compliant = backlash <= 3.0
    return {
        "log": [f"{UNISPSC_CODE}:calculate_precision"],
        "backlash_arcmin": backlash,
        "is_compliant": compliant,
    }


def synthesize_output(state: State) -> dict[str, Any]:
    """Generates the final procurement-ready specification for the robot gear."""
    is_ok = state.get("is_compliant", False)
    return {
        "log": [f"{UNISPSC_CODE}:synthesize_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "READY" if is_ok else "REJECTED_PRECISION_FAIL",
            "specs": {
                "profile": state.get("gear_profile"),
                "grade": state.get("material_grade"),
                "backlash": state.get("backlash_arcmin"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_profile", validate_profile)
_g.add_node("calculate_precision", calculate_precision)
_g.add_node("synthesize_output", synthesize_output)

_g.add_edge(START, "validate_profile")
_g.add_edge("validate_profile", "calculate_precision")
_g.add_edge("calculate_precision", "synthesize_output")
_g.add_edge("synthesize_output", END)

graph = _g.compile()
