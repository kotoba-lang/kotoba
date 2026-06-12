# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121505 — Acid Procurement (segment 15).

Bespoke graph logic for industrial acid acquisition and safety validation.
This agent handles hazmat compliance verification and storage allocation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121505"
UNISPSC_TITLE = "Acid Procurement"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    concentration_verified: bool
    hazmat_compliance_id: str
    storage_tank_allocation: str


def validate_hazmat_compliance(state: State) -> dict[str, Any]:
    """Verifies safety permits and chemical concentration specs."""
    inp = state.get("input") or {}
    permit = inp.get("permit_id", "PENDING")
    concentration = inp.get("molarity", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_hazmat_compliance"],
        "concentration_verified": concentration > 0.0,
        "hazmat_compliance_id": permit if permit != "PENDING" else "UNAUTHORIZED",
    }


def assign_containment_unit(state: State) -> dict[str, Any]:
    """Determines appropriate storage based on compliance status."""
    compliance_id = state.get("hazmat_compliance_id")
    is_valid = state.get("concentration_verified", False)

    if is_valid and compliance_id != "UNAUTHORIZED":
        unit = "BUNKER-7-CORROSIVE"
        msg = "allocation_success"
    else:
        unit = "NONE"
        msg = "allocation_denied"

    return {
        "log": [f"{UNISPSC_CODE}:{msg}"],
        "storage_tank_allocation": unit,
    }


def finalize_procurement_ledger(state: State) -> dict[str, Any]:
    """Records the procurement outcome in the agent state."""
    unit = state.get("storage_tank_allocation", "NONE")
    success = unit != "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_ledger"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": "APPROVED" if success else "REJECTED",
            "assigned_unit": unit,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_hazmat_compliance", validate_hazmat_compliance)
_g.add_node("assign_containment_unit", assign_containment_unit)
_g.add_node("finalize_procurement_ledger", finalize_procurement_ledger)

_g.add_edge(START, "validate_hazmat_compliance")
_g.add_edge("validate_hazmat_compliance", "assign_containment_unit")
_g.add_edge("assign_containment_unit", "finalize_procurement_ledger")
_g.add_edge("finalize_procurement_ledger", END)

graph = _g.compile()
