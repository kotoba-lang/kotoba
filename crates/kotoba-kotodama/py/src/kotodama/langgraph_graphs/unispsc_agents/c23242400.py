# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242400 — Machine (segment 23).

This bespoke LangGraph agent handles the lifecycle of industrial machinery,
managing states for identification, safety validation, and operational status.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242400"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Machine
    machine_id: str
    maintenance_status: str
    safety_check_passed: bool
    operating_hours: int
    thermal_signature: str


def diagnose_system(state: State) -> dict[str, Any]:
    """Identify the machine and capture initial telemetry."""
    inp = state.get("input") or {}
    m_id = inp.get("machine_id", "MCH-GENERIC-001")
    hours = inp.get("hours", 0)

    return {
        "log": [f"{UNISPSC_CODE}:diagnose_system -> machine:{m_id}"],
        "machine_id": m_id,
        "operating_hours": hours,
        "maintenance_status": "initializing",
    }


def safety_inspection(state: State) -> dict[str, Any]:
    """Verify safety protocols and operating constraints."""
    hours = state.get("operating_hours", 0)
    # Machines with over 10,000 hours require manual override or deep service
    safety_ok = hours < 10000
    thermal = "nominal" if safety_ok else "elevated"

    return {
        "log": [f"{UNISPSC_CODE}:safety_inspection -> safety_ok:{safety_ok}"],
        "safety_check_passed": safety_ok,
        "thermal_signature": thermal,
        "maintenance_status": "inspected",
    }


def operational_commit(state: State) -> dict[str, Any]:
    """Commit the machine to an operational state or flag for maintenance."""
    safety_ok = state.get("safety_check_passed", False)
    m_id = state.get("machine_id")

    status = "operational" if safety_ok else "maintenance_required"

    return {
        "log": [f"{UNISPSC_CODE}:operational_commit -> status:{status}"],
        "maintenance_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "machine_id": m_id,
            "did": UNISPSC_DID,
            "status": status,
            "ok": safety_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("diagnose", diagnose_system)
_g.add_node("inspect", safety_inspection)
_g.add_node("commit", operational_commit)

_g.add_edge(START, "diagnose")
_g.add_edge("diagnose", "inspect")
_g.add_edge("inspect", "commit")
_g.add_edge("commit", END)

graph = _g.compile()
