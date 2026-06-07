# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251810 — Die Procurement (segment 23).
Bespoke logic for industrial die tool acquisition and specification verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251810"
UNISPSC_TITLE = "Die Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251810"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Die Procurement
    spec_validated: bool
    die_material: str
    vendor_qualified: bool
    lead_time_estimate_days: int


def validate_specifications(state: State) -> dict[str, Any]:
    """Verify that the die design specifications meet manufacturing standards."""
    inp = state.get("input") or {}
    # Simulate validation of material and CAD references
    material = inp.get("material", "Tool Steel D2")
    has_specs = "dimensions" in inp or "cad_file_id" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "spec_validated": has_specs,
        "die_material": material
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Identify and qualify vendors capable of precision die fabrication."""
    if not state.get("spec_validated"):
        return {"log": [f"{UNISPSC_CODE}:evaluate_vendors:skipped"]}

    # Simulate vendor selection based on material requirements
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_qualified": True,
        "lead_time_estimate_days": 21
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement order and generate the result record."""
    is_ready = state.get("vendor_qualified", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "procurement_status": "authorized" if is_ready else "pending_info",
        "order_details": {
            "material": state.get("die_material"),
            "est_lead_time": state.get("lead_time_estimate_days"),
        },
        "ok": is_ready,
    }

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("evaluate_vendors", evaluate_vendors)
_g.add_node("execute_procurement", execute_procurement)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "evaluate_vendors")
_g.add_edge("evaluate_vendors", "execute_procurement")
_g.add_edge("execute_procurement", END)

graph = _g.compile()
