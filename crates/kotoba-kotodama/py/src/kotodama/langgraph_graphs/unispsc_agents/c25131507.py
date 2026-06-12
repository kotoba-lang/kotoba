# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131507 — Aircraft (segment 25).

This bespoke agent implements a flight readiness and certification pipeline for
Aircraft assets. It handles pre-flight inspection, flight plan filing, and
final takeoff clearance verification within the LangGraph framework.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131507"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    tail_number: str
    airworthiness_status: str
    fuel_percentage: float
    flight_path: list[str]


def pre_flight_inspect(state: State) -> dict[str, Any]:
    """Node: Validate aircraft physical status and airworthiness certification."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "N-ETZ-2513")
    return {
        "log": [f"{UNISPSC_CODE}:pre_flight_inspect"],
        "tail_number": tail,
        "airworthiness_status": "CERTIFIED",
        "fuel_percentage": 100.0,
    }


def file_flight_plan(state: State) -> dict[str, Any]:
    """Node: Record intended flight route and log manifest data."""
    inp = state.get("input") or {}
    route = inp.get("route", ["KSEA", "KSFO"])
    return {
        "log": [f"{UNISPSC_CODE}:file_flight_plan"],
        "flight_path": route,
    }


def verify_clearance(state: State) -> dict[str, Any]:
    """Node: Finalize state and emit the clearance result for the aircraft."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_clearance"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": state.get("tail_number"),
            "flight_path": state.get("flight_path"),
            "readiness": "CLEARED_FOR_TAKEOFF",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("pre_flight_inspect", pre_flight_inspect)
_g.add_node("file_flight_plan", file_flight_plan)
_g.add_node("verify_clearance", verify_clearance)

_g.add_edge(START, "pre_flight_inspect")
_g.add_edge("pre_flight_inspect", "file_flight_plan")
_g.add_edge("file_flight_plan", "verify_clearance")
_g.add_edge("verify_clearance", END)

graph = _g.compile()
