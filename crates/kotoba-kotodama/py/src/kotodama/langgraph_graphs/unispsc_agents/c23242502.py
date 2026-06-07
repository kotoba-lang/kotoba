# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242502 — Machine (segment 23).

Bespoke logic for industrial machinery management, focusing on operational
parameters, maintenance scheduling, and safety compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242502"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Machine
    operational_status: str
    maintenance_interval_hours: int
    serial_number: str
    safety_interlock_active: bool
    last_diagnostic_code: str


def initialize_machine(state: State) -> dict[str, Any]:
    """Validates input data and initializes the machine record state."""
    inp = state.get("input") or {}
    sn = inp.get("serial_number", "MACH-DEFAULT-99")
    maint = inp.get("maintenance_interval", 1000)

    return {
        "log": [f"{UNISPSC_CODE}:initialize_machine"],
        "serial_number": sn,
        "maintenance_interval_hours": maint,
        "operational_status": "initialized",
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Checks safety interlocks and diagnostic state."""
    # Simulate a safety check: failures for specific IDs
    is_safe = state.get("serial_number") != "MACH-CRITICAL-ERR"

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_interlock_active": is_safe,
        "operational_status": "ready" if is_safe else "blocked",
        "last_diagnostic_code": "OK" if is_safe else "ERR_INTERLOCK",
    }


def generate_report(state: State) -> dict[str, Any]:
    """Finalizes the machine status report with metadata."""
    status = state.get("operational_status")
    sn = state.get("serial_number")
    maint = state.get("maintenance_interval_hours")

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_id": sn,
            "status": status,
            "maint_interval": maint,
            "certified": status == "ready",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_machine)
_g.add_node("verify", verify_safety)
_g.add_node("report", generate_report)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "verify")
_g.add_edge("verify", "report")
_g.add_edge("report", END)

graph = _g.compile()
