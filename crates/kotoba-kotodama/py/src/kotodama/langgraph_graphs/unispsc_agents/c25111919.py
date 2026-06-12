# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111919 — Keel (segment 25).

Bespoke logic for keel structural validation, stress testing, and certification.
The keel is the primary structural member of a ship's hull, requiring
rigorous material and alignment verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111919"
UNISPSC_TITLE = "Keel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111919"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    material_spec: str
    hull_alignment_verified: bool
    stress_threshold_kn: float
    certification_status: str


def validate_material(state: State) -> dict[str, Any]:
    """Validates the metallurgical properties of the keel component."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    # Keels for high-performance vessels often require specific alloys
    is_valid = material in ["Marine Steel", "Alloy-705", "Carbon Steel"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_material - {material} (valid: {is_valid})"],
        "material_spec": material,
        "hull_alignment_verified": inp.get("alignment", 0.0) < 0.05,
    }


def test_structural_stress(state: State) -> dict[str, Any]:
    """Calculates maximum stress threshold for the longitudinal structure."""
    material = state.get("material_spec", "Unknown")
    # Base thresholds in kilonewtons
    thresholds = {"Marine Steel": 500.0, "Alloy-705": 750.0, "Carbon Steel": 400.0}
    limit = thresholds.get(material, 100.0)

    return {
        "log": [f"{UNISPSC_CODE}:test_structural_stress - limit: {limit}kN"],
        "stress_threshold_kn": limit,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Issues final certification based on alignment and stress tests."""
    aligned = state.get("hull_alignment_verified", False)
    threshold = state.get("stress_threshold_kn", 0.0)

    passed = aligned and threshold >= 400.0
    status = "CERTIFIED" if passed else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_component - status: {status}"],
        "certification_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "threshold_kn": threshold,
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("test_structural_stress", test_structural_stress)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "test_structural_stress")
_g.add_edge("test_structural_stress", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
