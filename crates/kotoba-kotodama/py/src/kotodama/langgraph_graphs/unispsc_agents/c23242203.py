# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242203 — Machine (segment 23).
Bespoke logic for industrial machine state management and diagnostic flow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242203"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242203"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for "Machine"
    machine_serial: str
    maintenance_status: str
    safety_flags: list[str]
    is_operational: bool


def initialize_unit(state: State) -> dict[str, Any]:
    """Extracts machine identity and resets safety flags."""
    inp = state.get("input") or {}
    serial = str(inp.get("serial", "UNIT-DEFAULT-00"))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_unit serial={serial}"],
        "machine_serial": serial,
        "safety_flags": [],
        "maintenance_status": "initializing",
    }


def run_diagnostics(state: State) -> dict[str, Any]:
    """Simulates system-level diagnostic checks on the machine."""
    serial = state.get("machine_serial", "")
    flags = []
    # Arbitrary domain logic for safety checks
    if "FAULT" in serial.upper():
        flags.append("CRITICAL_SYSTEM_ERROR")
    if len(serial) < 5:
        flags.append("INVALID_SERIAL_LENGTH")

    is_operational = len(flags) == 0
    return {
        "log": [f"{UNISPSC_CODE}:run_diagnostics count={len(flags)}"],
        "safety_flags": flags,
        "is_operational": is_operational,
        "maintenance_status": "operational" if is_operational else "maintenance_required",
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final machine state report for the result field."""
    is_op = state.get("is_operational", False)
    serial = state.get("machine_serial", "UNKNOWN")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_report status={state.get('maintenance_status')}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_id": serial,
            "health_score": 100 if is_op else 20,
            "flags": state.get("safety_flags", []),
            "ready": is_op,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_unit", initialize_unit)
_g.add_node("run_diagnostics", run_diagnostics)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "initialize_unit")
_g.add_edge("initialize_unit", "run_diagnostics")
_g.add_edge("run_diagnostics", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
