# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153505 — Tool (segment 23).

Bespoke logic for tool management, calibration, and maintenance tracking.
This graph handles the lifecycle of a generic industrial tool.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153505"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Tool"
    calibration_verified: bool
    maintenance_status: str
    operational_mode: str
    safety_interlock_active: bool


def inspect_tool(state: State) -> dict[str, Any]:
    """Inspects the tool for safety and maintenance compliance."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "standard")

    # Simulate a safety check based on input parameters
    safety_ok = inp.get("safety_override") is not True

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tool"],
        "calibration_verified": True,
        "maintenance_status": "nominal",
        "safety_interlock_active": safety_ok,
        "operational_mode": mode
    }


def configure_tool(state: State) -> dict[str, Any]:
    """Configures the tool based on the requested operational mode."""
    mode = state.get("operational_mode", "standard")
    interlock = state.get("safety_interlock_active", False)

    # Only allow configuration if safety interlock is active and mode is valid
    config_success = interlock and mode in ["standard", "precision", "high_capacity"]

    return {
        "log": [f"{UNISPSC_CODE}:configure_tool"],
        "maintenance_status": "active" if config_success else "fault",
    }


def dispatch_tool(state: State) -> dict[str, Any]:
    """Finalizes the tool state and prepares the execution result."""
    status = state.get("maintenance_status")
    success = status == "active"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_tool"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "operational" if success else "inhibited",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_tool)
_g.add_node("configure", configure_tool)
_g.add_node("dispatch", dispatch_tool)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
