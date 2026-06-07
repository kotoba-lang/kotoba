# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131902 — Helicopter (segment 25).

Bespoke LangGraph implementation for Helicopter assets, providing
stateful pre-flight verification, rotor systems testing, and
dispatch finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131902"
UNISPSC_TITLE = "Helicopter"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific helicopter state
    tail_number: str
    rotor_status: str
    fuel_level_percent: int
    avionics_cleared: bool
    flight_plan_filed: bool


def pre_flight_inspection(state: State) -> dict[str, Any]:
    """Initial node to parse input and set baseline helicopter parameters."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "N000-UNISPSC")
    fuel = inp.get("fuel", 100)

    return {
        "log": [f"{UNISPSC_CODE}:pre_flight_inspection: {tail}"],
        "tail_number": tail,
        "fuel_level_percent": fuel,
        "rotor_status": "standby",
        "avionics_cleared": False
    }


def systems_engagement_test(state: State) -> dict[str, Any]:
    """Secondary node simulating rotor torque and avionics health checks."""
    fuel = state.get("fuel_level_percent", 0)
    ready = fuel > 20

    return {
        "log": [f"{UNISPSC_CODE}:systems_engagement_test: fuel={fuel}% readiness={ready}"],
        "rotor_status": "spinning" if ready else "failure",
        "avionics_cleared": ready,
        "flight_plan_filed": True
    }


def dispatch_finalization(state: State) -> dict[str, Any]:
    """Final node preparing the execution result for the helicopter agent."""
    is_ready = state.get("avionics_cleared", False) and state.get("rotor_status") == "spinning"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_finalization: ready={is_ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": state.get("tail_number"),
            "operational_status": "deployed" if is_ready else "grounded",
            "success": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("pre_flight_inspection", pre_flight_inspection)
_g.add_node("systems_engagement_test", systems_engagement_test)
_g.add_node("dispatch_finalization", dispatch_finalization)

_g.add_edge(START, "pre_flight_inspection")
_g.add_edge("pre_flight_inspection", "systems_engagement_test")
_g.add_edge("systems_engagement_test", "dispatch_finalization")
_g.add_edge("dispatch_finalization", END)

graph = _g.compile()
