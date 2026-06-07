# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202500 — Aircraft (segment 25).

Bespoke graph logic for aircraft management, covering specification validation,
airworthiness verification, and flight authorization. This agent ensures that
aircraft entities conform to regulatory and operational standards within the
Etz Hayyim ecosystem.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202500"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tail_number: str
    airworthiness_status: str
    propulsion_type: str
    flight_plan_id: str


def validate_specs(state: State) -> dict[str, Any]:
    """Extracts and validates aircraft specifications from input."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "N-UNKNOWN")
    prop = inp.get("propulsion", "Jet")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs - {tail}"],
        "tail_number": tail,
        "propulsion_type": prop
    }


def verify_airworthiness(state: State) -> dict[str, Any]:
    """Simulates a check of maintenance logs and certification records."""
    tail = state.get("tail_number", "N-UNKNOWN")
    # In a real system, this would look up a registry; here we simulate success.
    status = "CERTIFIED" if tail != "N-UNKNOWN" else "PENDING_INSPECTION"

    return {
        "log": [f"{UNISPSC_CODE}:verify_airworthiness - status: {status}"],
        "airworthiness_status": status
    }


def authorize_flight(state: State) -> dict[str, Any]:
    """Finalizes the process and emits an authorization token."""
    tail = state.get("tail_number")
    status = state.get("airworthiness_status")
    fp_id = f"FP-{tail}-2026"

    authorized = status == "CERTIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_flight - {fp_id}"],
        "flight_plan_id": fp_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "authorization_id": fp_id if authorized else None,
            "ok": authorized,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_airworthiness", verify_airworthiness)
_g.add_node("authorize_flight", authorize_flight)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_airworthiness")
_g.add_edge("verify_airworthiness", "authorize_flight")
_g.add_edge("authorize_flight", END)

graph = _g.compile()
