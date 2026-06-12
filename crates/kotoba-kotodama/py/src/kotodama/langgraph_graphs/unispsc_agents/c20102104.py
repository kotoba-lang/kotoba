# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102104 — Precision (segment 20).

Bespoke graph logic for precision instruments and tools within the well drilling
and completion equipment domain. This agent manages calibration checks,
tolerance verification, and accuracy recording for high-precision drilling tools.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102104"
UNISPSC_TITLE = "Precision"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Precision tools
    calibration_verified: bool
    tolerance_microns: float
    accuracy_rating: str
    tool_serial_number: str


def validate_calibration(state: State) -> dict[str, Any]:
    """Ensures the precision tool is within its calibration window."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SN-UNKNOWN")
    # Simulate a lookup/check of calibration records
    is_valid = inp.get("calibration_current", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_calibration (tool: {serial})"],
        "calibration_verified": is_valid,
        "tool_serial_number": serial
    }


def verify_tolerance(state: State) -> dict[str, Any]:
    """Checks if the tool meets the required precision tolerances."""
    if not state.get("calibration_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:verify_tolerance skipped (unverified)"],
            "accuracy_rating": "FAIL"
        }

    # In a real scenario, this might involve checking sensor data
    tolerance = 0.05  # microns
    return {
        "log": [f"{UNISPSC_CODE}:verify_tolerance (limit: {tolerance})"],
        "tolerance_microns": tolerance,
        "accuracy_rating": "HIGH_PRECISION"
    }


def record_precision_data(state: State) -> dict[str, Any]:
    """Finalizes the precision report for the drilling operation."""
    success = state.get("calibration_verified") and state.get("accuracy_rating") != "FAIL"

    return {
        "log": [f"{UNISPSC_CODE}:record_precision_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial": state.get("tool_serial_number"),
            "accuracy": state.get("accuracy_rating"),
            "verified": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_calibration)
_g.add_node("verify", verify_tolerance)
_g.add_node("record", record_precision_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "record")
_g.add_edge("record", END)

graph = _g.compile()
