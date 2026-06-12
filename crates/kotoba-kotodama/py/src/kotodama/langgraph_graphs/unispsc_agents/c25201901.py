# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
# Note: In some environments 'operator.add' is used directly in Annotated.
# We import it to ensure 'operator.add' is available if referenced.
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201901"
UNISPSC_TITLE = "Aircraft System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Aircraft System
    tail_number: str
    avionics_status: str
    fuel_integrity_verified: bool
    safety_interlock_active: bool


def initialize_diagnostics(state: State) -> dict[str, Any]:
    """Sets up the initial diagnostic state for the aircraft system."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "AC-25201901")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_diagnostics"],
        "tail_number": tail,
        "avionics_status": "initializing",
        "safety_interlock_active": True,
    }


def verify_subsystems(state: State) -> dict[str, Any]:
    """Performs logic checks on avionics and fuel systems."""
    # Simulation of internal logic checking subsystems
    return {
        "log": [f"{UNISPSC_CODE}:verify_subsystems"],
        "avionics_status": "nominal",
        "fuel_integrity_verified": True,
    }


def finalize_clearance(state: State) -> dict[str, Any]:
    """Generates the final readiness result for the aircraft system agent."""
    tail = state.get("tail_number")
    status = state.get("avionics_status")
    fuel_ok = state.get("fuel_integrity_verified", False)

    is_ready = (status == "nominal") and fuel_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_clearance"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "readiness_certified": is_ready,
            "system_health": "GREEN" if is_ready else "YELLOW",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_diagnostics", initialize_diagnostics)
_g.add_node("verify_subsystems", verify_subsystems)
_g.add_node("finalize_clearance", finalize_clearance)

_g.add_edge(START, "initialize_diagnostics")
_g.add_edge("initialize_diagnostics", "verify_subsystems")
_g.add_edge("verify_subsystems", "finalize_clearance")
_g.add_edge("finalize_clearance", END)

graph = _g.compile()
