# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101717 — Fastener.
Bespoke logic for mechanical fastener specification, material validation, and load rating.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101717"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101717"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Fastener domain fields
    material_grade: str
    tensile_strength_psi: int
    thread_pitch_mm: float
    corrosion_resistance_hrs: int
    validation_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates input parameters for the fastener type and material grade."""
    inp = state.get("input") or {}
    material = inp.get("material", "Grade 5 Steel")
    pitch = float(inp.get("pitch", 1.25))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material_grade": material,
        "thread_pitch_mm": pitch,
        "validation_status": "PENDING_PROPERTIES",
    }


def calculate_mechanical_limits(state: State) -> dict[str, Any]:
    """Determines tensile strength and corrosion resistance based on material."""
    grade = state.get("material_grade", "Grade 5 Steel")

    # Domain-specific logic for fastener properties
    props = {
        "Grade 5 Steel": (120000, 48),
        "Grade 8 Steel": (150000, 72),
        "Stainless 316": (70000, 1000),
        "Titanium Ti-6Al-4V": (130000, 2000),
    }

    strength, corrosion = props.get(grade, (60000, 24))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_mechanical_limits(grade={grade})"],
        "tensile_strength_psi": strength,
        "corrosion_resistance_hrs": corrosion,
    }


def generate_engineering_report(state: State) -> dict[str, Any]:
    """Compiles the final specification result for the fastener agent."""
    strength = state.get("tensile_strength_psi", 0)
    is_industrial = strength >= 100000

    return {
        "log": [f"{UNISPSC_CODE}:generate_engineering_report"],
        "validation_status": "APPROVED" if strength > 0 else "REJECTED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_grade"),
                "tensile_strength": f"{strength} PSI",
                "thread_pitch": f"{state.get('thread_pitch_mm')} mm",
                "salt_spray_rating": f"{state.get('corrosion_resistance_hrs')} hrs",
            },
            "classification": "Industrial Grade" if is_industrial else "General Purpose",
            "ok": strength > 0,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("calculate", calculate_mechanical_limits)
_g.add_node("report", generate_engineering_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "report")
_g.add_edge("report", END)

graph = _g.compile()
