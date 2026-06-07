# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122702 — Robot (segment 20).

Bespoke logic for robot procurement and management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122702"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    serial_number: str
    firmware_version: str
    calibration_verified: bool
    diagnostic_status: str


def initialize_robot(state: State) -> dict[str, Any]:
    """Sets up the initial robot identification from input data."""
    inp = state.get("input") or {}
    sn = inp.get("serial_number", "SN-UNKNOWN")
    fw = inp.get("firmware", "v1.0.0")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_robot"],
        "serial_number": sn,
        "firmware_version": fw,
        "diagnostic_status": "initialized",
    }


def calibrate_sensors(state: State) -> dict[str, Any]:
    """Simulates a sensor calibration sequence based on firmware version."""
    fw = state.get("firmware_version", "")
    is_valid = fw.startswith("v")
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_sensors"],
        "calibration_verified": is_valid,
        "diagnostic_status": "calibrated" if is_valid else "calibration_failed",
    }


def prepare_manifest(state: State) -> dict[str, Any]:
    """Finalizes the robot data manifest for procurement emission."""
    is_ok = state.get("calibration_verified", False)
    sn = state.get("serial_number", "N/A")
    status = state.get("diagnostic_status", "unknown")
    return {
        "log": [f"{UNISPSC_CODE}:prepare_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial": sn,
            "diagnostic_status": status,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_robot)
_g.add_node("calibrate", calibrate_sensors)
_g.add_node("manifest", prepare_manifest)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "calibrate")
_g.add_edge("calibrate", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
