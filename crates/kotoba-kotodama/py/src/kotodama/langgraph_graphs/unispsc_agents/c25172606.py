# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172606 — Hood (segment 25).

Bespoke graph logic for vehicle hood component validation and certification.
This agent handles material inspection, latch mechanism verification, and
alignment tolerance checks within the Etz Hayyim vehicle manufacturing ontology.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172606"
UNISPSC_TITLE = "Hood"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state fields for "Hood"
    material_grade: str
    latch_security_verified: bool
    alignment_tolerance_mm: float
    surface_coating_type: str


def inspect_materials(state: State) -> dict[str, Any]:
    """Validates the raw material specifications for the hood assembly."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard-Steel")
    coating = inp.get("coating", "E-Coat")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_materials -> {grade}"],
        "material_grade": grade,
        "surface_coating_type": coating
    }


def verify_mechanicals(state: State) -> dict[str, Any]:
    """Simulates testing of the primary and secondary latch mechanisms."""
    # Logic: Verify alignment and latch engagement
    inp = state.get("input") or {}
    measured_offset = inp.get("measured_offset", 0.5)

    # We consider < 1.5mm within spec for vehicle hoods
    is_secure = measured_offset < 1.5

    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanicals -> offset:{measured_offset}mm"],
        "latch_security_verified": is_secure,
        "alignment_tolerance_mm": measured_offset
    }


def certify_component(state: State) -> dict[str, Any]:
    """Produces the final certification result for the vehicle component."""
    passed = state.get("latch_security_verified", False)
    grade = state.get("material_grade", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:certify_component -> status:{'PASS' if passed else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified_material": grade,
            "structural_integrity": passed,
            "timestamp_utc": "2026-05-23T14:00:00Z",
            "ok": passed
        }
    }


_g = StateGraph(State)

_g.add_node("inspect_materials", inspect_materials)
_g.add_node("verify_mechanicals", verify_mechanicals)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "inspect_materials")
_g.add_edge("inspect_materials", "verify_mechanicals")
_g.add_edge("verify_mechanicals", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
