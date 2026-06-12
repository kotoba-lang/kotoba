# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181501"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_input: float
    current_draw: float
    torque_nm: float
    position_feedback: float
    is_faulted: bool


def initialize_hardware(state: State) -> dict[str, Any]:
    """Initializes the actuator hardware and sets safety limits."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 24.0))
    is_faulted = voltage < 12.0 or voltage > 48.0

    return {
        "log": [f"{UNISPSC_CODE}:initialize_hardware -> voltage={voltage}V"],
        "voltage_input": voltage,
        "is_faulted": is_faulted,
    }


def calibrate_position(state: State) -> dict[str, Any]:
    """Performs zero-point calibration for the actuator encoder."""
    if state.get("is_faulted"):
        return {"log": [f"{UNISPSC_CODE}:calibrate_position -> skipped (fault)"]}

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_position -> centered"],
        "position_feedback": 0.0,
    }


def perform_actuation(state: State) -> dict[str, Any]:
    """Simulates the actuation cycle and monitors power consumption."""
    fault = state.get("is_faulted", False)
    v = state.get("voltage_input", 0.0)
    current = 0.5 if not fault else 0.0
    torque = 1.2 if not fault else 0.0

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "operational": not fault,
        "telemetry": {
            "voltage": v,
            "current": current,
            "torque": torque
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:perform_actuation -> result generated"],
        "result": res,
        "current_draw": current,
        "torque_nm": torque
    }


_g = StateGraph(State)

_g.add_node("init", initialize_hardware)
_g.add_node("calibrate", calibrate_position)
_g.add_node("actuate", perform_actuation)

_g.add_edge(START, "init")
_g.add_edge("init", "calibrate")
_g.add_edge("calibrate", "actuate")
_g.add_edge("actuate", END)

graph = _g.compile()
