# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111518 — Tension Procurement (segment 26).

Bespoke graph logic for Tension Procurement. This agent manages the lifecycle
of procuring tensioning equipment and services, ensuring specifications are met
and vendors are qualified within the power generation segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111518"
UNISPSC_TITLE = "Tension Procurement"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111518"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Tension Procurement
    required_load_kn: float
    vendor_compliance_verified: bool
    procurement_id: str
    material_grade: str


def analyze_spec(state: State) -> dict[str, Any]:
    """Validate the technical tension requirements from input."""
    inp = state.get("input") or {}
    load = float(inp.get("load_kn", 0.0))
    grade = str(inp.get("grade", "Standard"))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_spec -> load={load}kN, grade={grade}"],
        "required_load_kn": load,
        "material_grade": grade,
    }


def source_supplier(state: State) -> dict[str, Any]:
    """Simulate supplier vetting for the specified tension grade."""
    load = state.get("required_load_kn", 0.0)
    grade = state.get("material_grade", "Standard")
    # High load (>500kN) requires Premium material grade for compliance
    is_compliant = load < 500.0 or grade == "Premium"

    return {
        "log": [f"{UNISPSC_CODE}:source_supplier -> compliant={is_compliant}"],
        "vendor_compliance_verified": is_compliant,
        "procurement_id": f"PRQ-{UNISPSC_CODE}-101",
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalize the procurement result based on vetting."""
    verified = state.get("vendor_compliance_verified", False)
    status = "Approved" if verified else "Rejected"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order -> status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": status,
            "verified": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_spec", analyze_spec)
_g.add_node("source_supplier", source_supplier)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "analyze_spec")
_g.add_edge("analyze_spec", "source_supplier")
_g.add_edge("source_supplier", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
