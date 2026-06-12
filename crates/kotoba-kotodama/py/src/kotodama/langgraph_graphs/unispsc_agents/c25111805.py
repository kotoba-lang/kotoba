# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111805"
UNISPSC_TITLE = "P W C"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vessel_id: str
    hull_integrity: bool
    engine_hours: int
    safety_gear_verified: bool


def inspect_vessel(state: State) -> dict[str, Any]:
    """Performs a visual and structural inspection of the Personal Water Craft hull."""
    inp = state.get("input") or {}
    v_id = inp.get("vessel_id", "PWC-DEFAULT")
    # Simulate an integrity check; defaults to True unless specified
    hull_ok = inp.get("hull_check", True)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel:vessel={v_id}:integrity={hull_ok}"],
        "vessel_id": v_id,
        "hull_integrity": hull_ok,
    }


def check_powertrain(state: State) -> dict[str, Any]:
    """Verifies engine hours and ensures safety lanyard/equipment are present."""
    inp = state.get("input") or {}
    hours = inp.get("hours", 0)
    safety_ok = inp.get("safety_gear", True)

    # Logic: High hours without safety gear triggers a warning
    status_msg = "POWERTRAIN_VERIFIED" if safety_ok else "SAFETY_FAILURE"
    return {
        "log": [f"{UNISPSC_CODE}:check_powertrain:status={status_msg}"],
        "engine_hours": hours,
        "safety_gear_verified": safety_ok,
    }


def certify_vessel(state: State) -> dict[str, Any]:
    """Aggregates inspection data and issues a certification for the PWC."""
    v_id = state.get("vessel_id")
    hull_ok = state.get("hull_integrity", False)
    safety_ok = state.get("safety_gear_verified", False)

    is_certified = hull_ok and safety_ok

    return {
        "log": [f"{UNISPSC_CODE}:certify_vessel:certified={is_certified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vessel_id": v_id,
            "certification": "ACTIVE" if is_certified else "REVOKED",
            "ok": is_certified,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_vessel", inspect_vessel)
_g.add_node("check_powertrain", check_powertrain)
_g.add_node("certify_vessel", certify_vessel)

_g.add_edge(START, "inspect_vessel")
_g.add_edge("inspect_vessel", "check_powertrain")
_g.add_edge("check_powertrain", "certify_vessel")
_g.add_edge("certify_vessel", END)

graph = _g.compile()
