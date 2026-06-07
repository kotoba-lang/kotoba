# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131600"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tail_number: str
    airworthiness_certified: bool
    maintenance_last_check: str
    fuel_level_percent: float


def validate_airframe(state: State) -> dict[str, Any]:
    """Validate the aircraft tail number and basic registration."""
    inp = state.get("input") or {}
    tail_number = inp.get("tail_number", "UNKNOWN")
    # Simulate airworthiness verification logic (e.g., FAA registration check)
    is_certified = tail_number.startswith("N") or tail_number.startswith("G")
    return {
        "log": [f"{UNISPSC_CODE}:validate_airframe"],
        "tail_number": tail_number,
        "airworthiness_certified": is_certified,
    }


def check_serviceability(state: State) -> dict[str, Any]:
    """Perform a mock serviceability check on maintenance logs and fuel status."""
    return {
        "log": [f"{UNISPSC_CODE}:check_serviceability"],
        "maintenance_last_check": "2026-05-20",
        "fuel_level_percent": 95.0,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Emit the final flight readiness result based on state checks."""
    is_certified = state.get("airworthiness_certified", False)
    fuel_level = state.get("fuel_level_percent", 0.0)
    ready = is_certified and fuel_level > 10.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": state.get("tail_number"),
            "dispatch_ready": ready,
            "status": "APPROVED" if ready else "GROUNDED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_airframe", validate_airframe)
_g.add_node("check_serviceability", check_serviceability)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "validate_airframe")
_g.add_edge("validate_airframe", "check_serviceability")
_g.add_edge("check_serviceability", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
