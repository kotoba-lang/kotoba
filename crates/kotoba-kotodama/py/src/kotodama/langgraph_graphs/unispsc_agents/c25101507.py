# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101507 — Vehicle Procure (segment 25).
Bespoke logic for orchestrating vehicle acquisition and procurement workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101507"
UNISPSC_TITLE = "Vehicle Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Vehicle Procure
    specifications_vetted: bool
    procurement_id: str
    vendor_auth_status: str
    delivery_terms_accepted: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input requirements for vehicle procurement."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    # Simple logic: ensure there is a vehicle type defined
    vetted = "vehicle_type" in specs
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "specifications_vetted": vetted,
        "procurement_id": f"REQ-{UNISPSC_CODE}-{hash(str(specs)) % 10000}",
    }


def authorize_vendor(state: State) -> dict[str, Any]:
    """Checks the authorization status of the vehicle vendor."""
    vetted = state.get("specifications_vetted", False)
    status = "AUTHORIZED" if vetted else "PENDING_REVIEWS"
    return {
        "log": [f"{UNISPSC_CODE}:authorize_vendor"],
        "vendor_auth_status": status,
        "delivery_terms_accepted": vetted,
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and generates the result artifact."""
    authorized = state.get("vendor_auth_status") == "AUTHORIZED"
    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "COMPLETED" if authorized else "FAILED",
            "ok": authorized,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("authorize", authorize_vendor)
_g.add_node("execute", execute_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "authorize")
_g.add_edge("authorize", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
