# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23211100 — Fastener (segment 23).

Bespoke graph logic for industrial fastener specification and certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23211100"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23211100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Fastener
    material_grade: str
    tensile_strength_mpa: float
    thread_pitch_mm: float
    is_certified: bool
    inspection_passed: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Inspects the fastener specification for required mechanical properties."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "Unknown"))
    pitch = float(inp.get("pitch", 0.0))

    # Basic validation of mechanical specs
    passed = material != "Unknown" and pitch > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec: {material} (passed={passed})"],
        "material_grade": material,
        "thread_pitch_mm": pitch,
        "inspection_passed": passed,
    }


def analyze_load(state: State) -> dict[str, Any]:
    """Calculates theoretical tensile strength based on material grade."""
    material = state.get("material_grade", "Unknown")

    # Mock lookup for industrial fastener grades
    strength_map = {
        "Grade 8.8": 800.0,
        "Grade 10.9": 1040.0,
        "Grade 12.9": 1220.0,
        "Stainless A2-70": 700.0,
    }
    strength = strength_map.get(material, 400.0)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load: {strength} MPa"],
        "tensile_strength_mpa": strength,
        "is_certified": strength >= 700.0,
    }


def certify_fastener(state: State) -> dict[str, Any]:
    """Finalizes the Fastener actor state and emits the result."""
    passed = state.get("inspection_passed", False)
    certified = state.get("is_certified", False)
    strength = state.get("tensile_strength_mpa", 0.0)

    success = passed and certified

    return {
        "log": [f"{UNISPSC_CODE}:certify_fastener: certified={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tensile_strength_mpa": strength,
            "grade": state.get("material_grade"),
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("analyze_load", analyze_load)
_g.add_node("certify_fastener", certify_fastener)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "analyze_load")
_g.add_edge("analyze_load", "certify_fastener")
_g.add_edge("certify_fastener", END)

graph = _g.compile()
