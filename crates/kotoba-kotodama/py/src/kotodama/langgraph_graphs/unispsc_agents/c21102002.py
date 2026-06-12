# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102002 — Sorting Machine.
Bespoke logic for industrial sorting equipment automation and telemetry.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102002"
UNISPSC_TITLE = "Sorting Machine"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Sorting Machine
    batch_token: str
    target_bin_count: int
    throughput_rate: float
    calibration_offset: float
    system_status: str


def validate_configuration(state: State) -> dict[str, Any]:
    """Validates the input configuration for the sorting run."""
    inp = state.get("input") or {}
    token = inp.get("batch_id", "SYS-ALPHA-99")
    bins = inp.get("bins", 12)

    return {
        "log": [f"{UNISPSC_CODE}:validate_configuration -> {token}"],
        "batch_token": token,
        "target_bin_count": bins,
        "system_status": "READY",
    }


def perform_calibration(state: State) -> dict[str, Any]:
    """Executes optical sensor calibration routines."""
    # Simulation logic for calibration drift based on bin complexity
    offset = (state.get("target_bin_count", 1) * 0.0042) % 0.05

    return {
        "log": [f"{UNISPSC_CODE}:perform_calibration -> offset {offset:.4f}"],
        "calibration_offset": offset,
        "system_status": "CALIBRATED",
    }


def simulate_sort_cycle(state: State) -> dict[str, Any]:
    """Calculates throughput based on bin count and calibration accuracy."""
    bins = state.get("target_bin_count", 1)
    offset = state.get("calibration_offset", 0.0)

    # Base rate of 500 items/min, degraded by complexity (bins) and offset
    rate = (500.0 / (1.0 + (bins * 0.05))) * (1.0 - offset)

    return {
        "log": [f"{UNISPSC_CODE}:simulate_sort_cycle -> {rate:.2f} ppm"],
        "throughput_rate": rate,
        "system_status": "RUNNING",
    }


def compile_machine_report(state: State) -> dict[str, Any]:
    """Generates the final operation report for the sorting machine."""
    return {
        "log": [f"{UNISPSC_CODE}:compile_machine_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "batch": state.get("batch_token"),
                "bins_active": state.get("target_bin_count"),
                "throughput_ppm": state.get("throughput_rate"),
                "accuracy_offset": state.get("calibration_offset"),
                "final_state": "SUCCESS",
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_configuration)
_g.add_node("calibrate", perform_calibration)
_g.add_node("sort", simulate_sort_cycle)
_g.add_node("report", compile_machine_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "sort")
_g.add_edge("sort", "report")
_g.add_edge("report", END)

graph = _g.compile()
