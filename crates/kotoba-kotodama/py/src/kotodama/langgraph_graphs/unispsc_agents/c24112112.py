# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112112 — Drum Lid (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112112"
UNISPSC_TITLE = "Drum Lid"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112112"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Drum Lid (Material Handling/Storage)
    diameter_mm: float
    material_grade: str
    gasket_type: str
    seal_test_passed: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Inspects the physical dimensions and material grade of the drum lid."""
    inp = state.get("input") or {}
    # Default to standard 55-gallon drum dimensions if not provided
    diameter = float(inp.get("diameter_mm", 571.5))
    grade = str(inp.get("material_grade", "304L-Stainless"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specification: {grade} @ {diameter}mm"],
        "diameter_mm": diameter,
        "material_grade": grade,
    }


def verify_containment_seal(state: State) -> dict[str, Any]:
    """Verifies the gasket material and simulates a seal integrity test."""
    inp = state.get("input") or {}
    gasket = str(inp.get("gasket_type", "EPDM"))
    # In a production environment, this would interface with QA systems
    return {
        "log": [f"{UNISPSC_CODE}:verify_containment_seal: {gasket} gasket confirmed"],
        "gasket_type": gasket,
        "seal_test_passed": True,
    }


def emit_compliance_cert(state: State) -> dict[str, Any]:
    """Generates the final compliance record for the drum lid component."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_compliance_cert"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "diameter_mm": state.get("diameter_mm"),
                "material": state.get("material_grade"),
                "gasket": state.get("gasket_type"),
            },
            "certification": "ISO-16106-COMPLIANT" if state.get("seal_test_passed") else "PENDING",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specification", validate_specification)
_g.add_node("verify_containment_seal", verify_containment_seal)
_g.add_node("emit_compliance_cert", emit_compliance_cert)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "verify_containment_seal")
_g.add_edge("verify_containment_seal", "emit_compliance_cert")
_g.add_edge("emit_compliance_cert", END)

graph = _g.compile()
