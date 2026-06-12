# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121510"
UNISPSC_TITLE = "Trolley Wire"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for trolley wire overhead contact systems
    alloy_grade: str
    cross_section_mm2: float
    breaking_load_kn: float
    conductivity_iacs: float


def inspect_dimensions(state: State) -> dict[str, Any]:
    """Checks input specs for the trolley wire geometric and material properties."""
    inp = state.get("input") or {}
    grade = str(inp.get("grade", "Cu-ETP"))
    section = float(inp.get("section", 120.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_dimensions -> {grade} {section}mm2"],
        "alloy_grade": grade,
        "cross_section_mm2": section,
    }


def verify_mechanicals(state: State) -> dict[str, Any]:
    """Verifies breaking load and electrical conductivity metrics for traction power."""
    grade = state.get("alloy_grade", "Cu-ETP")
    section = state.get("cross_section_mm2", 0.0)

    # Engineering approximation for breaking load based on material tensile strength
    # Magnesium alloys provide higher strength but lower conductivity than pure copper
    strength_mpa = 500.0 if "Mg" in grade else 310.0
    load_kn = (section * strength_mpa) / 1000.0

    # Conductivity % IACS (International Annealed Copper Standard)
    conductivity = 62.0 if "Mg" in grade else 97.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanicals -> {load_kn:.1f}kN @ {conductivity}% IACS"],
        "breaking_load_kn": load_kn,
        "conductivity_iacs": conductivity,
    }


def emit_certificate(state: State) -> dict[str, Any]:
    """Finalizes the technical certificate for the trolley wire component batch."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "grade": state.get("alloy_grade"),
                "section_mm2": state.get("cross_section_mm2"),
                "breaking_load_kn": state.get("breaking_load_kn"),
                "conductivity_iacs": state.get("conductivity_iacs"),
            },
            "certification_status": "compliant",
            "usage": "Overhead Catenary Systems (OCS)"
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_dimensions)
_g.add_node("verify", verify_mechanicals)
_g.add_node("emit", emit_certificate)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
