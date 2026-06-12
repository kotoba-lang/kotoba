# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241801 — Machine (segment 23).
Bespoke logic for industrial machine lifecycle management and diagnostic verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241801"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    power_status: str
    maintenance_status: str
    diagnostic_code: str
    calibration_verified: bool


def diagnose_machine(state: State) -> dict[str, Any]:
    """Inspects the machine state and performs initial diagnostics."""
    inp = state.get("input") or {}
    power = inp.get("power", "OFF")
    return {
        "log": [f"{UNISPSC_CODE}:diagnose_machine"],
        "power_status": power,
        "maintenance_status": "READY" if power == "ON" else "MAINTENANCE_REQUIRED",
        "diagnostic_code": "SYS-OK" if power == "ON" else "SYS-ERR-OFFLINE",
    }


def calibrate_machine(state: State) -> dict[str, Any]:
    """Verifies and updates calibration parameters for the machine."""
    is_ready = state.get("maintenance_status") == "READY"
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_machine"],
        "calibration_verified": is_ready,
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Finalizes the machine operation and emits the result state."""
    success = state.get("calibration_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "power_status": state.get("power_status"),
            "diagnostic_code": state.get("diagnostic_code"),
            "operational": success,
            "status": "OPERATIONAL" if success else "IDLE",
        },
    }


_g = StateGraph(State)

_g.add_node("diagnose", diagnose_machine)
_g.add_node("calibrate", calibrate_machine)
_g.add_node("finalize", finalize_operation)

_g.add_edge(START, "diagnose")
_g.add_edge("diagnose", "calibrate")
_g.add_edge("calibrate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
