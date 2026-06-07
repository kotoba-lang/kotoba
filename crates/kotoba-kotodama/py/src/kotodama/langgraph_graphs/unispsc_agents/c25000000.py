# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25000000"
UNISPSC_TITLE = "Vehicle Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25000000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Vehicle procurement domain specific fields
    fleet_requirement_id: str
    emissions_compliance_met: bool
    procurement_budget_status: str
    delivery_schedule_confirmed: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Initial check of fleet specifications and requirement IDs."""
    inp = state.get("input") or {}
    req_id = inp.get("fleet_id", "VPR-DEFAULT")
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "fleet_requirement_id": req_id,
        "procurement_budget_status": "Pending Review",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies that the requested vehicles meet segment 25 regulatory standards."""
    # Logic transition based on dummy input presence
    is_compliant = bool(state.get("fleet_requirement_id"))
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "emissions_compliance_met": is_compliant,
        "procurement_budget_status": "Authorized" if is_compliant else "Flagged",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement result and sets delivery flags."""
    budget_ok = state.get("procurement_budget_status") == "Authorized"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "delivery_schedule_confirmed": budget_ok,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "fleet_id": state.get("fleet_requirement_id"),
            "compliance_verified": state.get("emissions_compliance_met"),
            "status": "Ready for delivery" if budget_ok else "Hold",
            "ok": budget_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
