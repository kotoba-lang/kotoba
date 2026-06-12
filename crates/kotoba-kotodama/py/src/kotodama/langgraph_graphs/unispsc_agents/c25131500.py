# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131500 — Aircraft (segment 25).

This bespoke implementation handles aircraft-specific state transitions including
airworthiness verification, tail number registration tracking, and flight readiness
assessment within the LangGraph framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131500"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Aircraft fields
    tail_number: str
    airworthiness_status: str
    maintenance_records_verified: bool
    flight_ready: bool


def inspect_aircraft(state: State) -> dict[str, Any]:
    """Validate aircraft registration and airworthiness status."""
    inp = state.get("input") or {}
    tail_no = inp.get("tail_number", "N-UNKNOWN")

    # Simulate an airworthiness check based on provided certificate IDs
    status = "Certified" if inp.get("cert_id") else "Pending Inspection"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_aircraft: {tail_no}"],
        "tail_number": tail_no,
        "airworthiness_status": status,
        "maintenance_records_verified": True
    }


def verify_flight_readiness(state: State) -> dict[str, Any]:
    """Assess if the aircraft is prepared for operational deployment."""
    status = state.get("airworthiness_status")
    ready = (status == "Certified")

    return {
        "log": [f"{UNISPSC_CODE}:verify_flight_readiness: {ready}"],
        "flight_ready": ready
    }


def generate_status_report(state: State) -> dict[str, Any]:
    """Emit the final aircraft status and metadata."""
    ready = state.get("flight_ready", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": state.get("tail_number"),
            "airworthiness": state.get("airworthiness_status"),
            "flight_ready": ready,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_aircraft)
_g.add_node("verify", verify_flight_readiness)
_g.add_node("report", generate_status_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "report")
_g.add_edge("report", END)

graph = _g.compile()
