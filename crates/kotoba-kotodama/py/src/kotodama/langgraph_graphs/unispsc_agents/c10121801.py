# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10121801 — Fertilizer (segment 10).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10121801"
UNISPSC_TITLE = "Fertilizer"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10121801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Fertilizer-specific state fields
    npk_composition: str
    safety_data_verified: bool
    batch_tracking_id: str
    target_moisture_level: float


def inspect_composition(state: State) -> dict[str, Any]:
    """Analyze the N-P-K (Nitrogen-Phosphorus-Potassium) ratio of the fertilizer."""
    inp = state.get("input") or {}
    # Default to 10-10-10 if not provided in input
    npk = inp.get("npk", "10-10-10")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "npk_composition": npk,
        "batch_tracking_id": str(inp.get("batch_id", "B-DEFAULT-001")),
    }


def validate_safety_compliance(state: State) -> dict[str, Any]:
    """Check against agricultural safety standards for hazardous components."""
    inp = state.get("input") or {}
    # Fertilizers can contain oxidizing agents or high concentrations of nutrients
    is_hazardous = inp.get("hazardous", False)
    has_sds = "sds_document" in inp or "sds_link" in inp

    # Requirement: If flagged as hazardous, MUST have Safety Data Sheet (SDS) metadata
    compliance = not is_hazardous or has_sds

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_compliance"],
        "safety_data_verified": compliance,
        "target_moisture_level": float(inp.get("moisture", 5.0)),
    }


def generate_fertilizer_manifest(state: State) -> dict[str, Any]:
    """Produce the final product manifest with compliance details."""
    safe = state.get("safety_data_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:generate_fertilizer_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "npk": state.get("npk_composition"),
            "batch": state.get("batch_tracking_id"),
            "moisture": state.get("target_moisture_level"),
            "compliance_passed": safe,
            "ok": safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_composition", inspect_composition)
_g.add_node("validate_safety_compliance", validate_safety_compliance)
_g.add_node("generate_fertilizer_manifest", generate_fertilizer_manifest)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "validate_safety_compliance")
_g.add_edge("validate_safety_compliance", "generate_fertilizer_manifest")
_g.add_edge("generate_fertilizer_manifest", END)

graph = _g.compile()
