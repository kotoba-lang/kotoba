# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131701 — Bomber (segment 25).

Bespoke LangGraph implementation for military bomber aircraft lifecycle management,
handling pre-flight inspections, payload configuration, and mission readiness.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131701"
UNISPSC_TITLE = "Bomber"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain-specific fields for "Bomber"
    airframe_integrity: bool
    payload_status: str
    avionics_diagnostic: str
    fuel_load_kg: float


def inspect_airframe(state: State) -> dict[str, Any]:
    """Perform structural and avionics checks on the bomber."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel_request", 45000.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_airframe"],
        "airframe_integrity": True,
        "avionics_diagnostic": "ALL_SYSTEMS_GO",
        "fuel_load_kg": fuel,
    }


def arm_ordnance(state: State) -> dict[str, Any]:
    """Configure and verify the mission payload."""
    inp = state.get("input") or {}
    mission_type = inp.get("mission_type", "strategic")
    payload = "READY" if state.get("airframe_integrity") else "ABORTED"

    return {
        "log": [f"{UNISPSC_CODE}:arm_ordnance"],
        "payload_status": f"{mission_type.upper()}_{payload}",
    }


def finalize_sortie(state: State) -> dict[str, Any]:
    """Generate final mission readiness certificate."""
    ready = (
        state.get("airframe_integrity") is True and
        "READY" in state.get("payload_status", "")
    )

    return {
        "log": [f"{UNISPSC_CODE}:finalize_sortie"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_ready": ready,
            "diagnostics": {
                "fuel": state.get("fuel_load_kg"),
                "avionics": state.get("avionics_diagnostic"),
                "payload": state.get("payload_status"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_airframe)
_g.add_node("arm", arm_ordnance)
_g.add_node("finalize", finalize_sortie)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "arm")
_g.add_edge("arm", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
