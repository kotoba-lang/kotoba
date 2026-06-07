# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121905 — Actuator (segment 20).

Bespoke LangGraph implementation for mechanical actuation control systems.
This agent handles signal validation, dynamics computation, and cycle execution.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121905"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121905"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    voltage_input: float
    target_position: float
    mechanical_load: float
    safety_status: str


def validate_input(state: State) -> dict[str, Any]:
    """Validates voltage levels and safety interlocks for the actuator hardware."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 0.0))
    load = float(inp.get("load", 5.0))

    # Actuator safety logic: verify within operating 0-24V range
    status = "READY" if 0.0 <= voltage <= 24.0 else "VOLTAGE_OUT_OF_RANGE"

    return {
        "log": [f"{UNISPSC_CODE}:validate_input: status={status}"],
        "voltage_input": voltage,
        "mechanical_load": load,
        "safety_status": status
    }


def compute_dynamics(state: State) -> dict[str, Any]:
    """Calculates target mechanical position based on input control signal."""
    voltage = state.get("voltage_input", 0.0)
    # Position mapping: 0V (closed) to 24V (fully open/100mm)
    if state.get("safety_status") == "READY":
        target = (voltage / 24.0) * 100.0
    else:
        target = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_dynamics: target_pos={target}mm"],
        "target_position": target
    }


def execute_cycle(state: State) -> dict[str, Any]:
    """Simulates the physical movement and returns final telemetry state."""
    status = state.get("safety_status")
    pos = state.get("target_position", 0.0)
    load = state.get("mechanical_load", 0.0)

    success = (status == "READY")

    return {
        "log": [f"{UNISPSC_CODE}:execute_cycle: completion_success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_position_mm": pos,
                "observed_load_kg": load,
                "status_code": status
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("compute", compute_dynamics)
_g.add_node("execute", execute_cycle)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
