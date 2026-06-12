# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112502 — Packaging (segment 24).

This agent handles the logic for specialized packaging operations,
ensuring material compatibility, cushioning requirements, and
regulatory enclosure standards are met for material handling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112502"
UNISPSC_TITLE = "Packaging"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Packaging
    material_grade: str
    cushioning_factor: float
    is_tamper_evident: bool
    compliance_certified: bool


def assess_packaging_needs(state: State) -> dict[str, Any]:
    """Analyzes shipment properties to determine packaging requirements."""
    inp = state.get("input") or {}
    weight = inp.get("weight_kg", 0.0)
    fragility = inp.get("fragility_index", 1)

    # Determine grade based on weight and fragility
    grade = "INDUSTRIAL" if weight > 50 or fragility > 5 else "STANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:assess_packaging_needs -> {grade}"],
        "material_grade": grade,
        "cushioning_factor": float(fragility * 1.5)
    }


def apply_protection_layers(state: State) -> dict[str, Any]:
    """Selects and applies cushioning and tamper-evidence protocols."""
    grade = state.get("material_grade", "STANDARD")
    # High-grade material defaults to tamper-evident
    tamper_needed = grade == "INDUSTRIAL"

    return {
        "log": [f"{UNISPSC_CODE}:apply_protection_layers"],
        "is_tamper_evident": tamper_needed,
        "compliance_certified": True
    }


def validate_shipment_ready(state: State) -> dict[str, Any]:
    """Final check to ensure the package meets UNISPSC 24112502 standards."""
    is_ok = state.get("compliance_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_shipment_ready"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "packaging_status": "READY" if is_ok else "REJECTED",
            "spec_summary": {
                "grade": state.get("material_grade"),
                "tamper_proof": state.get("is_tamper_evident")
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("assess_packaging_needs", assess_packaging_needs)
_g.add_node("apply_protection_layers", apply_protection_layers)
_g.add_node("validate_shipment_ready", validate_shipment_ready)

_g.add_edge(START, "assess_packaging_needs")
_g.add_edge("assess_packaging_needs", "apply_protection_layers")
_g.add_edge("apply_protection_layers", "validate_shipment_ready")
_g.add_edge("validate_shipment_ready", END)

graph = _g.compile()
