# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102004 — Tractor (segment 21).

Bespoke graph logic for tractor operation simulation, safety verification,
and status tracking.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102004"
UNISPSC_TITLE = "Tractor"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain state for Tractor
    engine_status: str
    fuel_level: float
    attachment_type: str
    safety_lock_engaged: bool
    maintenance_required: bool


def inspect(state: State) -> dict[str, Any]:
    """Perform pre-operation inspection of the tractor."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel_level", 0.85))
    safety = bool(inp.get("safety_lock", True))
    maint = fuel < 0.1

    return {
        "log": [f"{UNISPSC_CODE}:inspect - fuel={fuel:.2f}, safety={safety}"],
        "fuel_level": fuel,
        "safety_lock_engaged": safety,
        "maintenance_required": maint,
        "attachment_type": inp.get("attachment", "none"),
    }


def service(state: State) -> dict[str, Any]:
    """Engage engine and verify operational parameters."""
    if state.get("maintenance_required"):
        return {
            "log": [f"{UNISPSC_CODE}:service - ABORTED: Maintenance required"],
            "engine_status": "fault",
        }

    if state.get("safety_lock_engaged"):
        return {
            "log": [f"{UNISPSC_CODE}:service - Engine inhibited by safety lock"],
            "engine_status": "standby",
        }

    return {
        "log": [f"{UNISPSC_CODE}:service - Engine started successfully"],
        "engine_status": "running",
    }


def dispatch(state: State) -> dict[str, Any]:
    """Finalize state and emit the operation results."""
    engine = state.get("engine_status", "off")
    attachment = state.get("attachment_type", "none")

    return {
        "log": [f"{UNISPSC_CODE}:dispatch - tractor {engine} with {attachment}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": engine,
            "active_attachment": attachment,
            "ok": engine == "running",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect)
_g.add_node("service", service)
_g.add_node("dispatch", dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "service")
_g.add_edge("service", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
