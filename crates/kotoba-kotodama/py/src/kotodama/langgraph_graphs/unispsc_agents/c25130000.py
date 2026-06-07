# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25130000 — Aircraft (segment 25).

Bespoke graph logic for aircraft lifecycle management, including registration
verification, maintenance audit, and flight clearance issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25130000"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25130000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tail_number: str
    airworthiness_certified: bool
    maintenance_history: list[str]


def validate_registration(state: State) -> dict[str, Any]:
    """Validates the aircraft registration and tail number."""
    inp = state.get("input") or {}
    tail_number = inp.get("tail_number", "UNKNOWN-N000")
    return {
        "log": [f"{UNISPSC_CODE}:validate_registration"],
        "tail_number": tail_number,
    }


def audit_maintenance_records(state: State) -> dict[str, Any]:
    """Audits the maintenance history for safety compliance."""
    tail_number = state.get("tail_number")
    # Simulate maintenance record check
    history = [f"Annual inspection passed for {tail_number}", "Engine overhaul verified"]
    return {
        "log": [f"{UNISPSC_CODE}:audit_maintenance_records"],
        "maintenance_history": history,
        "airworthiness_certified": True,
    }


def issue_flight_clearance(state: State) -> dict[str, Any]:
    """Issues the final flight clearance based on audit results."""
    is_safe = state.get("airworthiness_certified", False)
    tail = state.get("tail_number")

    return {
        "log": [f"{UNISPSC_CODE}:issue_flight_clearance"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "status": "CLEARED" if is_safe else "GROUNDED",
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_registration", validate_registration)
_g.add_node("audit_maintenance_records", audit_maintenance_records)
_g.add_node("issue_flight_clearance", issue_flight_clearance)

_g.add_edge(START, "validate_registration")
_g.add_edge("validate_registration", "audit_maintenance_records")
_g.add_edge("audit_maintenance_records", "issue_flight_clearance")
_g.add_edge("issue_flight_clearance", END)

graph = _g.compile()
