# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174405 — Cluster (segment 25).

Bespoke graph logic for the automotive instrument cluster, handling
diagnostic validation, gauge calibration, and display rendering.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174405"
UNISPSC_TITLE = "Cluster"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174405"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Instrument Cluster
    diagnostics_pass: bool
    calibration_status: str
    active_indicators: list[str]
    system_voltage: float


def diagnostic_check(state: State) -> dict[str, Any]:
    """Perform initial self-test and voltage sweep for the cluster."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 12.6))

    # Check if voltage is within operating range (9V - 16V)
    is_valid = 9.0 <= voltage <= 16.0

    return {
        "log": [f"{UNISPSC_CODE}:diagnostic_check"],
        "diagnostics_pass": is_valid,
        "system_voltage": voltage,
        "active_indicators": ["ABS", "CHECK_ENGINE"] if not is_valid else []
    }


def calibrate_gauges(state: State) -> dict[str, Any]:
    """Verify stepper motor positioning for speedometer and tachometer."""
    if not state.get("diagnostics_pass", False):
        return {
            "log": [f"{UNISPSC_CODE}:calibrate_gauges:skipped"],
            "calibration_status": "FAILED_DIAGNOSTICS"
        }

    # Simulate calibration logic
    inp = state.get("input") or {}
    mode = inp.get("calibration_mode", "standard")

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_gauges:success"],
        "calibration_status": f"CALIBRATED_{mode.upper()}"
    }


def render_display(state: State) -> dict[str, Any]:
    """Finalize the digital/analog output state for the driver interface."""
    diag = state.get("diagnostics_pass", False)
    cal = state.get("calibration_status", "PENDING")

    success = diag and "CALIBRATED" in cal

    return {
        "log": [f"{UNISPSC_CODE}:render_display"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if success else "FAULT",
            "voltage": state.get("system_voltage"),
            "indicators": state.get("active_indicators", []),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("diagnostic_check", diagnostic_check)
_g.add_node("calibrate_gauges", calibrate_gauges)
_g.add_node("render_display", render_display)

_g.add_edge(START, "diagnostic_check")
_g.add_edge("diagnostic_check", "calibrate_gauges")
_g.add_edge("calibrate_gauges", "render_display")
_g.add_edge("render_display", END)

graph = _g.compile()
