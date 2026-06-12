# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101609 — Chemical Procurement.
Bespoke logic for managing chemical acquisition, safety verification, and regulatory compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101609"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101609"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Chemical Procurement
    sds_status: str
    hazard_class: str
    supplier_vetted: bool
    procurement_phase: str


def validate_safety_requirements(state: State) -> dict[str, Any]:
    """Verify Safety Data Sheet (SDS) availability and identify hazard classification."""
    inp = state.get("input") or {}
    hazard = inp.get("hazard_class", "non-hazardous")
    sds_id = inp.get("sds_id")

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_requirements"],
        "sds_status": "verified" if sds_id else "missing",
        "hazard_class": hazard,
        "procurement_phase": "safety_validated",
    }


def process_procurement_request(state: State) -> dict[str, Any]:
    """Vette chemical supplier and check for acquisition restrictions."""
    inp = state.get("input") or {}
    supplier_id = inp.get("supplier_id")
    # Simulation: Suppliers starting with 'V' are pre-vetted
    is_vetted = bool(supplier_id and supplier_id.startswith("V"))

    return {
        "log": [f"{UNISPSC_CODE}:process_procurement_request"],
        "supplier_vetted": is_vetted,
        "procurement_phase": "supplier_processed",
    }


def emit_procurement_result(state: State) -> dict[str, Any]:
    """Finalize the chemical procurement state and return execution results."""
    sds_ok = state.get("sds_status") == "verified"
    vetted = state.get("supplier_vetted", False)
    hazard = state.get("hazard_class", "unknown")

    success = sds_ok and vetted
    return {
        "log": [f"{UNISPSC_CODE}:emit_procurement_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "sds_verified": sds_ok,
            "supplier_approved": vetted,
            "hazard_class": hazard,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety", validate_safety_requirements)
_g.add_node("process_request", process_procurement_request)
_g.add_node("emit_result", emit_procurement_result)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "process_request")
_g.add_edge("process_request", "emit_result")
_g.add_edge("emit_result", END)

graph = _g.compile()
