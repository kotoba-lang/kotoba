# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153500 — Robot Procurement (segment 23).

Bespoke logic for robot procurement processes, including specification verification,
budget approval, and final order placement for industrial or specialized robotics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153500"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Robot Procurement
    procurement_id: str
    robot_spec: dict[str, Any]
    budget_approved: bool
    vendor_id: str


def initialize_procurement(state: State) -> dict[str, Any]:
    """Initialize the procurement workflow and assign a tracking ID."""
    inp = state.get("input") or {}
    proc_id = inp.get("request_id", "REQ-ROBOT-UNSPECIFIED")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_procurement:{proc_id}"],
        "procurement_id": proc_id,
        "robot_spec": inp.get("specification", {}),
    }


def verify_specifications(state: State) -> dict[str, Any]:
    """Verify that robot specifications meet safety and operational standards."""
    spec = state.get("robot_spec") or {}
    # Simple validation: requires a model name and payload capacity
    is_valid = bool(spec.get("model")) and "payload_kg" in spec
    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications:valid={is_valid}"],
        "vendor_id": "VEND-DEFAULT-ROBOTICS" if is_valid else "UNASSIGNED",
    }


def approve_budget(state: State) -> dict[str, Any]:
    """Simulate budget review and approval for the procurement request."""
    vendor = state.get("vendor_id")
    # Budget is approved if a valid vendor was assigned during verification
    approved = vendor is not None and vendor != "UNASSIGNED"
    return {
        "log": [f"{UNISPSC_CODE}:approve_budget:approved={approved}"],
        "budget_approved": approved,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Compile the final procurement result and order details."""
    approved = state.get("budget_approved", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "procurement_id": state.get("procurement_id"),
            "status": "ORDER_PLACED" if approved else "SPECIFICATION_REJECTED",
            "ok": approved,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_procurement)
_g.add_node("verify", verify_specifications)
_g.add_node("budget", approve_budget)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "verify")
_g.add_edge("verify", "budget")
_g.add_edge("budget", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
