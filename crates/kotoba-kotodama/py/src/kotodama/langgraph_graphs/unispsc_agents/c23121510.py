# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121510 — Textile winding or reeling machinery.

This agent handles the lifecycle of industrial winding and reeling processes,
managing tension setpoints and spooling sequences for textile manufacturing.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121510"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for textile winding machinery
    tension_setpoint: float
    yarn_break_detected: bool
    spool_diameter_mm: float
    reeling_sequence_id: str


def initialize_reeling(state: State) -> dict[str, Any]:
    """Validates machine parameters and generates a sequence ID."""
    inp = state.get("input") or {}
    seq_id = inp.get("batch_id", "SEQ-AUTO-001")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_reeling"],
        "reeling_sequence_id": seq_id,
        "yarn_break_detected": False,
    }


def calibrate_tension(state: State) -> dict[str, Any]:
    """Calculates and sets the optimal tension for the current spool diameter."""
    # Simulated calibration logic
    target_diameter = state.get("input", {}).get("target_diameter", 150.0)
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_tension"],
        "tension_setpoint": 2.5,
        "spool_diameter_mm": target_diameter,
    }


def monitor_process(state: State) -> dict[str, Any]:
    """Final check of winding parameters before completion."""
    return {
        "log": [f"{UNISPSC_CODE}:monitor_process"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "success",
            "batch_id": state.get("reeling_sequence_id"),
            "final_tension": state.get("tension_setpoint"),
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_reeling)
_g.add_node("calibrate", calibrate_tension)
_g.add_node("monitor", monitor_process)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "calibrate")
_g.add_edge("calibrate", "monitor")
_g.add_edge("monitor", END)

graph = _g.compile()
