# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201504"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tail_number: str
    flight_hours: float
    airworthiness_status: str
    maintenance_interval_hours: float


def validate_registration(state: State) -> dict[str, Any]:
    """Inspects the input for tail number and initialization data."""
    inp = state.get("input") or {}
    tail_number = inp.get("tail_number", "N-GENERIC")
    hours = float(inp.get("flight_hours", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_registration:{tail_number}"],
        "tail_number": tail_number,
        "flight_hours": hours,
        "maintenance_interval_hours": 100.0,
    }


def check_airworthiness(state: State) -> dict[str, Any]:
    """Determines if the aircraft is fit for flight based on logged hours."""
    hours = state.get("flight_hours", 0.0)
    interval = state.get("maintenance_interval_hours", 100.0)
    status = "AIRWORTHY" if hours < interval else "MAINTENANCE_REQUIRED"
    return {
        "log": [f"{UNISPSC_CODE}:check_airworthiness:{status}"],
        "airworthiness_status": status,
    }


def finalize_status(state: State) -> dict[str, Any]:
    """Packages the final aircraft status and registry record."""
    status = state.get("airworthiness_status")
    tail = state.get("tail_number")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "airworthiness": status,
            "certified": status == "AIRWORTHY",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_registration", validate_registration)
_g.add_node("check_airworthiness", check_airworthiness)
_g.add_node("finalize_status", finalize_status)

_g.add_edge(START, "validate_registration")
_g.add_edge("validate_registration", "check_airworthiness")
_g.add_edge("check_airworthiness", "finalize_status")
_g.add_edge("finalize_status", END)

graph = _g.compile()
