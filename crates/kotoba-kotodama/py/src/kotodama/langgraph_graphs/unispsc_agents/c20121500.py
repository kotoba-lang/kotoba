# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121500 — Fastener (segment 20).
Bespoke logic for industrial fasteners, specifying material and load verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121500"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fastener procurement
    material_grade: str
    thread_pitch_verified: bool
    tensile_strength_mpa: int
    corrosion_resistant: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the basic dimensional and material constraints of the fastener."""
    inp = state.get("input") or {}
    material = inp.get("material", "Grade 2 Steel")
    pitch = inp.get("pitch", "standard")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_grade": material,
        "thread_pitch_verified": pitch in ["standard", "fine", "extra-fine"],
    }


def assess_mechanical_limits(state: State) -> dict[str, Any]:
    """Calculates mechanical limits based on material grade and verified pitch."""
    grade = state.get("material_grade", "Grade 2 Steel")

    # Empirical mapping for common bolt/screw materials
    mechanical_data = {
        "Grade 2 Steel": (510, False),
        "Grade 5 Steel": (830, False),
        "Grade 8 Steel": (1030, False),
        "Stainless 304": (515, True),
        "Stainless 316": (515, True),
    }

    strength, corrosion = mechanical_data.get(grade, (400, False))

    return {
        "log": [f"{UNISPSC_CODE}:assess_mechanical_limits"],
        "tensile_strength_mpa": strength,
        "corrosion_resistant": corrosion,
    }


def finalize_inventory_record(state: State) -> dict[str, Any]:
    """Produces the final verified fastener record for the design system."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec_summary": {
                "material": state.get("material_grade"),
                "tensile_strength_mpa": state.get("tensile_strength_mpa"),
                "corrosion_resistance": "High" if state.get("corrosion_resistant") else "Standard",
                "pitch_valid": state.get("thread_pitch_verified"),
            },
            "status": "APPROVED" if state.get("thread_pitch_verified") else "SPEC_UNVERIFIED",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("assess", assess_mechanical_limits)
_g.add_node("finalize", finalize_inventory_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
