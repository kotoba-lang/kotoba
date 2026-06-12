# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25102105 — Tractor (segment 25).

Bespoke graph logic for managing tractor maintenance and deployment state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25102105"
UNISPSC_TITLE = "Tractor"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25102105"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Tractor
    engine_hours: float
    maintenance_needed: bool
    attachment_type: str
    fuel_level_percent: float


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Node to inspect the tractor's mechanical state from input telemetry."""
    inp = state.get("input") or {}
    hours = float(inp.get("engine_hours", 0.0))
    fuel = float(inp.get("fuel_level", 100.0))

    # Simple logic: maintenance every 500 hours
    needs_service = (hours % 500) > 450 or hours == 0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle"],
        "engine_hours": hours,
        "fuel_level_percent": fuel,
        "maintenance_needed": needs_service,
        "attachment_type": inp.get("attachment", "none")
    }


def perform_service(state: State) -> dict[str, Any]:
    """Node to handle maintenance flag and prep for deployment."""
    status = "Maintenance deferred"
    if state.get("maintenance_needed"):
        status = "Maintenance scheduled"

    return {
        "log": [f"{UNISPSC_CODE}:perform_service - {status}"],
    }


def deploy_tractor(state: State) -> dict[str, Any]:
    """Final node to emit the operational status and metadata."""
    ready = state.get("fuel_level_percent", 0) > 10 and not state.get("maintenance_needed")

    return {
        "log": [f"{UNISPSC_CODE}:deploy_tractor"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "deployment_ready": ready,
            "telemetry_summary": {
                "hours": state.get("engine_hours"),
                "fuel": state.get("fuel_level_percent"),
                "attachment": state.get("attachment_type")
            },
            "ok": True
        }
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_vehicle)
_g.add_node("service", perform_service)
_g.add_node("deploy", deploy_tractor)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "service")
_g.add_edge("service", "deploy")
_g.add_edge("deploy", END)

graph = _g.compile()
