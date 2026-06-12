# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101903 — Snowmobile (segment 25).

Bespoke logic for validating chassis integrity and configuring
winter-readiness parameters for snowmobile assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101903"
UNISPSC_TITLE = "Snowmobile"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Snowmobile
    chassis_serial: str
    engine_inspection_status: str
    track_pattern: str
    is_winter_certified: bool


def inspect_chassis(state: State) -> dict[str, Any]:
    """Inspects the snowmobile chassis and initializes record."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SNW-2026-000")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_chassis"],
        "chassis_serial": serial,
        "engine_inspection_status": "PENDING"
    }


def verify_engine(state: State) -> dict[str, Any]:
    """Performs a virtual engine verification based on serial prefix."""
    serial = state.get("chassis_serial", "")
    status = "VERIFIED" if serial.startswith("SNW") else "REJECTED"
    return {
        "log": [f"{UNISPSC_CODE}:verify_engine"],
        "engine_inspection_status": status
    }


def configure_track(state: State) -> dict[str, Any]:
    """Configures the track pattern for specific terrain types."""
    inp = state.get("input") or {}
    pattern = inp.get("terrain", "powder")
    return {
        "log": [f"{UNISPSC_CODE}:configure_track"],
        "track_pattern": f"{pattern}_optimized"
    }


def certify_vehicle(state: State) -> dict[str, Any]:
    """Finalizes certification and prepares the dispatch result."""
    engine_ok = state.get("engine_inspection_status") == "VERIFIED"
    track_ok = "track_pattern" in state
    certified = engine_ok and track_ok

    return {
        "log": [f"{UNISPSC_CODE}:certify_vehicle"],
        "is_winter_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "serial": state.get("chassis_serial"),
            "status": "READY" if certified else "INCOMPLETE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_chassis", inspect_chassis)
_g.add_node("verify_engine", verify_engine)
_g.add_node("configure_track", configure_track)
_g.add_node("certify_vehicle", certify_vehicle)

_g.add_edge(START, "inspect_chassis")
_g.add_edge("inspect_chassis", "verify_engine")
_g.add_edge("verify_engine", "configure_track")
_g.add_edge("configure_track", "certify_vehicle")
_g.add_edge("certify_vehicle", END)

graph = _g.compile()
