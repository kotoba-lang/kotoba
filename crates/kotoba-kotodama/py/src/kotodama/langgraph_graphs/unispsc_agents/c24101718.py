# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101718 — Conveyor (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101718"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101718"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    belt_velocity: float
    load_detected: bool
    safety_circuit_closed: bool
    diverter_gate_position: str


def check_safety(state: State) -> dict[str, Any]:
    """Verify that the conveyor safety circuit is closed before operation."""
    inp = state.get("input") or {}
    # Simulate a safety check: circuit is closed unless E-stop is triggered
    circuit_ok = inp.get("emergency_stop_triggered") is not True
    return {
        "log": [f"{UNISPSC_CODE}:check_safety: circuit_closed={circuit_ok}"],
        "safety_circuit_closed": circuit_ok,
    }


def configure_drive(state: State) -> dict[str, Any]:
    """Set the motor speed and diverter gate based on input requirements."""
    if not state.get("safety_circuit_closed"):
        return {"log": [f"{UNISPSC_CODE}:configure_drive: aborted due to safety circuit"]}

    inp = state.get("input") or {}
    velocity = float(inp.get("target_velocity", 0.75))
    gate = inp.get("route_destination", "primary_sorting")
    load = inp.get("load_weight", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:configure_drive: v={velocity} gate={gate} load={load}"],
        "belt_velocity": velocity,
        "diverter_gate_position": gate,
        "load_detected": load,
    }


def run_conveyance(state: State) -> dict[str, Any]:
    """Execute the movement of material and report final status."""
    v = state.get("belt_velocity", 0.0)
    gate = state.get("diverter_gate_position", "none")
    safety = state.get("safety_circuit_closed", False)
    load = state.get("load_detected", False)

    success = safety and v > 0 and load

    return {
        "log": [f"{UNISPSC_CODE}:run_conveyance: transfer_complete={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation": "material_handling",
            "telemetry": {
                "velocity_m_s": v,
                "exit_gate": gate,
                "safety_ok": safety,
                "load_transported": load
            },
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("check_safety", check_safety)
_g.add_node("configure_drive", configure_drive)
_g.add_node("run_conveyance", run_conveyance)

_g.add_edge(START, "check_safety")
_g.add_edge("check_safety", "configure_drive")
_g.add_edge("configure_drive", "run_conveyance")
_g.add_edge("run_conveyance", END)

graph = _g.compile()
