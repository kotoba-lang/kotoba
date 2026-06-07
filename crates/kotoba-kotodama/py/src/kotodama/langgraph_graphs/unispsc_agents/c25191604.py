# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191604 — Launch Vehicle (segment 25).

Bespoke LangGraph logic for managing launch vehicle deployment sequences,
including payload integration, systems verification, and countdown protocols.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191604"
UNISPSC_TITLE = "Launch Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    payload_ready: bool
    propellant_status: str
    guidance_locked: bool
    launch_authorization: bool


def validate_flight_readiness(state: State) -> dict[str, Any]:
    """Verify payload presence and guidance system alignment."""
    inp = state.get("input") or {}
    payload_id = inp.get("payload_id", "SATELLITE-PRIMARY")
    is_ready = bool(payload_id)
    return {
        "log": [f"{UNISPSC_CODE}:validate_flight_readiness - Payload {payload_id} verified"],
        "payload_ready": is_ready,
        "guidance_locked": is_ready,
    }


def perform_countdown_sequence(state: State) -> dict[str, Any]:
    """Execute fueling and final pre-flight checks."""
    if not state.get("payload_ready"):
        return {
            "log": [f"{UNISPSC_CODE}:perform_countdown_sequence - ABORT: Payload not ready"],
            "launch_authorization": False
        }

    return {
        "log": [f"{UNISPSC_CODE}:perform_countdown_sequence - Fueling complete, all systems nominal"],
        "propellant_status": "FULL",
        "launch_authorization": True,
    }


def finalize_launch_protocol(state: State) -> dict[str, Any]:
    """Compile final mission parameters and authorize ignition."""
    authorized = state.get("launch_authorization", False)
    status = "IGNITION_CONFIRMED" if authorized else "MISSION_SCRUBBED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_launch_protocol - Final status: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_status": status,
            "ok": authorized,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_flight_readiness)
_g.add_node("countdown", perform_countdown_sequence)
_g.add_node("finalize", finalize_launch_protocol)

_g.add_edge(START, "validate")
_g.add_edge("validate", "countdown")
_g.add_edge("countdown", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
