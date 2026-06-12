# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191508 — Jetway (segment 25).

Bespoke LangGraph logic for managing passenger boarding bridge operations,
ensuring safe docking, extension parameters, and safety system verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191508"
UNISPSC_TITLE = "Jetway"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Jetway operations
    aircraft_model: str
    extension_distance_m: float
    auto_leveling_active: bool
    canopy_deployed: bool
    safety_lock_status: str


def initialize_docking(state: State) -> dict[str, Any]:
    """Identifies the target aircraft and initializes docking parameters."""
    inp = state.get("input") or {}
    model = inp.get("aircraft_model", "B737-800")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_docking: target={model}"],
        "aircraft_model": model,
        "safety_lock_status": "DISENGAGED",
    }


def deploy_bridge(state: State) -> dict[str, Any]:
    """Calculates and executes bridge extension and canopy deployment."""
    model = state.get("aircraft_model", "unknown")
    # Simulate logic where wide-body aircraft require longer bridge extension
    dist = 18.5 if any(w in model for w in ["747", "777", "A350", "A380"]) else 12.2
    return {
        "log": [f"{UNISPSC_CODE}:deploy_bridge: dist={dist}m"],
        "extension_distance_m": dist,
        "auto_leveling_active": True,
        "canopy_deployed": True,
    }


def finalize_connection(state: State) -> dict[str, Any]:
    """Verifies alignment and engages safety locks for passenger transit."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_connection: locks engaged"],
        "safety_lock_status": "ENGAGED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "BOARDING_READY",
            "telemetry": {
                "extension": state.get("extension_distance_m"),
                "auto_level": state.get("auto_leveling_active"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_docking", initialize_docking)
_g.add_node("deploy_bridge", deploy_bridge)
_g.add_node("finalize_connection", finalize_connection)

_g.add_edge(START, "initialize_docking")
_g.add_edge("initialize_docking", "deploy_bridge")
_g.add_edge("deploy_bridge", "finalize_connection")
_g.add_edge("finalize_connection", END)

graph = _g.compile()
