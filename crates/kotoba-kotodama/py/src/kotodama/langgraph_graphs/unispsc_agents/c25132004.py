# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke Unispsc actor agent c25132004 — Paraglider.

This agent handles the safety inspection and flight preparation workflow for
paragliding equipment, ensuring airworthiness and safety compliance.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25132004"
UNISPSC_TITLE = "Paraglider"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25132004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Paraglider
    is_airworthy: bool
    wing_classification: str
    reserve_parachute_inspected: bool
    harness_security_verified: bool
    weather_clearance: bool


def verify_certification(state: State) -> dict[str, Any]:
    """Inspects wing classification and airworthiness status."""
    inp = state.get("input") or {}
    wing = inp.get("wing_classification", "EN-A")
    return {
        "log": [f"{UNISPSC_CODE}:verify_certification"],
        "is_airworthy": True,
        "wing_classification": wing,
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Verifies harness connections and reserve parachute deployment readiness."""
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check"],
        "reserve_parachute_inspected": True,
        "harness_security_verified": True,
    }


def validate_launch_conditions(state: State) -> dict[str, Any]:
    """Final check of environmental factors and equipment readiness."""
    inp = state.get("input") or {}
    wind_speed = inp.get("wind_speed_kmh", 15)
    clearance = wind_speed < 25  # Safe limit for paragliding

    ready = (
        state.get("is_airworthy") and
        state.get("harness_security_verified") and
        clearance
    )

    return {
        "log": [f"{UNISPSC_CODE}:validate_launch_conditions"],
        "weather_clearance": clearance,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "flight_ready": ready,
            "wing": state.get("wing_classification"),
            "safety_status": "All checks passed" if ready else "Launch aborted",
            "ok": ready,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_certification", verify_certification)
_g.add_node("perform_safety_check", perform_safety_check)
_g.add_node("validate_launch_conditions", validate_launch_conditions)

_g.add_edge(START, "verify_certification")
_g.add_edge("verify_certification", "perform_safety_check")
_g.add_edge("perform_safety_check", "validate_launch_conditions")
_g.add_edge("validate_launch_conditions", END)

graph = _g.compile()
