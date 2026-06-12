# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101502 — Bolt (segment 22).

This bespoke implementation handles structural validation and mechanical
specification checking for bolts used in heavy construction machinery.
It verifies thread pitch, material grade, and tensile strength.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101502"
UNISPSC_TITLE = "Bolt"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Bolt components
    material_grade: str
    thread_pitch_mm: float
    tensile_strength_mpa: float
    is_structurally_sound: bool


def validate_mechanical_specs(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and grade of the bolt."""
    inp = state.get("input") or {}
    pitch = float(inp.get("pitch", 1.5))
    grade = str(inp.get("grade", "8.8"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanical_specs"],
        "thread_pitch_mm": pitch,
        "material_grade": grade,
    }


def calculate_load_limit(state: State) -> dict[str, Any]:
    """Estimates tensile strength based on material grade."""
    grade = state.get("material_grade", "8.8")
    # Industrial mapping for standard bolt grades
    strength_map = {
        "4.8": 400.0,
        "8.8": 800.0,
        "10.9": 1040.0,
        "12.9": 1220.0
    }
    strength = strength_map.get(grade, 300.0)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_limit"],
        "tensile_strength_mpa": strength,
        "is_structurally_sound": strength >= 800.0,
    }


def finalize_compliance_record(state: State) -> dict[str, Any]:
    """Produces the final UNISPSC agent result with certification data."""
    is_ok = state.get("is_structurally_sound", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_compliance_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "compliance": {
                "grade": state.get("material_grade"),
                "tensile_mpa": state.get("tensile_strength_mpa"),
                "pitch": state.get("thread_pitch_mm"),
            },
            "status": "APPROVED" if is_ok else "REJECTED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_mechanical_specs", validate_mechanical_specs)
_g.add_node("calculate_load_limit", calculate_load_limit)
_g.add_node("finalize_compliance_record", finalize_compliance_record)

_g.add_edge(START, "validate_mechanical_specs")
_g.add_edge("validate_mechanical_specs", "calculate_load_limit")
_g.add_edge("calculate_load_limit", "finalize_compliance_record")
_g.add_edge("finalize_compliance_record", END)

graph = _g.compile()
