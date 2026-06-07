# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111910 — Ramp Procurement (segment 25).

Bespoke LangGraph agent logic for the procurement of industrial and vehicle
loading ramps. This agent validates technical specifications, evaluates
vendor suitability, and generates procurement outcomes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111910"
UNISPSC_TITLE = "Ramp Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111910"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Ramp Procurement
    load_capacity_tons: float
    material_type: str
    safety_certification_verified: bool
    vendor_id: str


def evaluate_requirements(state: State) -> dict[str, Any]:
    """Validates the technical load and material requirements for the ramp."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity_tons", 0.0))
    material = inp.get("material", "steel")

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_requirements"],
        "load_capacity_tons": capacity,
        "material_type": material,
        "safety_certification_verified": capacity > 0 and len(material) > 0,
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Identifies a suitable vendor based on material and capacity."""
    # Logic to select a vendor; here we simulate selecting a primary supplier
    material = state.get("material_type", "unknown")
    v_id = f"VND-{material.upper()}-001"

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "vendor_id": v_id,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement result and PO status."""
    is_valid = state.get("safety_certification_verified", False)
    v_id = state.get("vendor_id", "N/A")

    procurement_status = "APPROVED" if is_valid else "REJECTED_INSUFFICIENT_SPECS"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vendor_assigned": v_id,
            "status": procurement_status,
            "ok": is_valid,
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate_requirements", evaluate_requirements)
_g.add_node("source_vendor", source_vendor)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "evaluate_requirements")
_g.add_edge("evaluate_requirements", "source_vendor")
_g.add_edge("source_vendor", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
