# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101703 — Machine (segment 22).

Bespoke graph logic for machine lifecycle management. This agent handles
diagnostic checks, operational configuration, and task execution for
heavy machinery assets within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101703"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Machine
    machine_asset_id: str
    diagnostic_report: dict[str, Any]
    calibration_index: float
    safety_interlock_verified: bool


def inspect_asset(state: State) -> dict[str, Any]:
    """Checks the machine's physical and digital identifiers."""
    inp = state.get("input") or {}
    asset_id = inp.get("asset_id", "M-DEFAULT-001")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_asset: Asset {asset_id} identified."],
        "machine_asset_id": asset_id,
        "safety_interlock_verified": True,
    }


def calibrate_parameters(state: State) -> dict[str, Any]:
    """Applies operational parameters to the machine state."""
    inp = state.get("input") or {}
    target_precision = inp.get("precision", 0.98)
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_parameters: Target precision set to {target_precision}"],
        "calibration_index": target_precision,
        "diagnostic_report": {"last_calibration": "success", "firmware_version": "2.4.1"},
    }


def run_cycle(state: State) -> dict[str, Any]:
    """Executes the machine operation cycle and emits the outcome."""
    asset_id = state.get("machine_asset_id")
    safe = state.get("safety_interlock_verified", False)
    cal = state.get("calibration_index", 0.0)

    operational_success = safe and (cal > 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:run_cycle: Operation success: {operational_success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "execution": {
                "asset_id": asset_id,
                "status": "COMPLETED" if operational_success else "FAILED",
                "telemetry": {"precision": cal, "safety_interlock": safe}
            },
            "ok": operational_success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_asset", inspect_asset)
_g.add_node("calibrate_parameters", calibrate_parameters)
_g.add_node("run_cycle", run_cycle)

_g.add_edge(START, "inspect_asset")
_g.add_edge("inspect_asset", "calibrate_parameters")
_g.add_edge("calibrate_parameters", "run_cycle")
_g.add_edge("run_cycle", END)

graph = _g.compile()
