# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242602 — Machine (segment 23).

Bespoke graph logic for industrial machinery processing, handling
calibration, safety verification, and operational telemetry.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242602"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    machine_serial: str
    safety_check_passed: bool
    calibration_value: float
    operational_mode: str


def inspect_safety(state: State) -> dict[str, Any]:
    """Verify safety interlocks and machine serial integrity."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SN-UNKNOWN")
    interlock = inp.get("safety_lock", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety"],
        "machine_serial": serial,
        "safety_check_passed": bool(interlock)
    }


def calibrate_unit(state: State) -> dict[str, Any]:
    """Apply calibration offsets to the machine logic."""
    if not state.get("safety_check_passed"):
        return {"log": [f"{UNISPSC_CODE}:calibrate_unit:skipped_unsafe"]}

    inp = state.get("input") or {}
    offset = float(inp.get("offset", 0.0))
    mode = str(inp.get("mode", "STANDBY"))

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_unit:applied_offset_{offset}"],
        "calibration_value": offset,
        "operational_mode": mode
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Emit final operational status and machine telemetry."""
    ok = state.get("safety_check_passed", False)
    serial = state.get("machine_serial", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_serial": serial,
            "status": "OPERATIONAL" if ok else "FAULT_LOCKED",
            "telemetry": {
                "cal": state.get("calibration_value", 0.0),
                "mode": state.get("operational_mode", "OFFLINE")
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_safety", inspect_safety)
_g.add_node("calibrate_unit", calibrate_unit)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "inspect_safety")
_g.add_edge("inspect_safety", "calibrate_unit")
_g.add_edge("calibrate_unit", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
