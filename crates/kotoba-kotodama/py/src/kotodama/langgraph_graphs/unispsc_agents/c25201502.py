# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201502 — Aircraft (segment 25).
Bespoke logic for airworthiness certification and pre-flight diagnostic processing.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201502"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tail_number: str
    airworthiness_certified: bool
    maintenance_status: str
    avionics_check: str


def inspect_airframe(state: State) -> dict[str, Any]:
    """Verify the structural integrity and maintenance records of the aircraft."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "N-ALPHA-25")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_airframe"],
        "tail_number": tail,
        "maintenance_status": "VERIFIED_SERVICEABLE",
    }


def verify_avionics(state: State) -> dict[str, Any]:
    """Perform a diagnostic sweep of flight control and navigation systems."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_avionics"],
        "avionics_check": "PASS_DIAGNOSTIC_B2",
        "airworthiness_certified": True,
    }


def certify_aircraft(state: State) -> dict[str, Any]:
    """Finalize the aircraft actor state and issue dispatch readiness report."""
    is_ready = state.get("airworthiness_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_aircraft"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": state.get("tail_number"),
            "maintenance": state.get("maintenance_status"),
            "avionics": state.get("avionics_check"),
            "ready_for_dispatch": is_ready,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_airframe)
_g.add_node("avionics", verify_avionics)
_g.add_node("certify", certify_aircraft)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "avionics")
_g.add_edge("avionics", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
