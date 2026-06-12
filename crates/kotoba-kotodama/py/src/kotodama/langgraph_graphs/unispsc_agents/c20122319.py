# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122319 — Robot Part (segment 20).
Bespoke logic for robot part validation, material inspection, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122319"
UNISPSC_TITLE = "Robot Part"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122319"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Robot Part
    part_serial_number: str
    material_analysis: dict[str, float]
    quality_clearance: bool
    structural_integrity_score: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications and extracts part metadata."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SN-PENDING")
    materials = inp.get("materials", {"aluminum": 0.85, "steel": 0.15})
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "part_serial_number": serial,
        "material_analysis": materials,
    }


def inspect_materials(state: State) -> dict[str, Any]:
    """Simulates a non-destructive testing (NDT) inspection of the part materials."""
    analysis = state.get("material_analysis", {})
    # Simple logic: ensure no hazardous materials for this specific robot part class
    has_mercury = analysis.get("mercury", 0.0) > 0.001
    score = 0.98 if not has_mercury else 0.35

    return {
        "log": [f"{UNISPSC_CODE}:inspect_materials"],
        "quality_clearance": not has_mercury,
        "structural_integrity_score": score,
    }


def certify_part(state: State) -> dict[str, Any]:
    """Finalizes the workflow and emits the certification result."""
    is_cleared = state.get("quality_clearance", False)
    score = state.get("structural_integrity_score", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_part"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial_number": state.get("part_serial_number"),
            "integrity_score": score,
            "certified": is_cleared and score > 0.8,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("inspect_materials", inspect_materials)
_g.add_node("certify_part", certify_part)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "inspect_materials")
_g.add_edge("inspect_materials", "certify_part")
_g.add_edge("certify_part", END)

graph = _g.compile()
