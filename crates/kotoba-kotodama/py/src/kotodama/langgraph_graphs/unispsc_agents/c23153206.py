# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153206"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153206"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Actuator
    control_signal_volts: float
    current_load_nm: float
    actuation_position_pct: float
    safety_interlock_engaged: bool
    calibration_offset: float


def evaluate_signal(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    signal = float(inp.get("signal", 0.0))
    safety = bool(inp.get("safety_clear", True))
    offset = float(inp.get("offset", 0.05))

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_signal(sig={signal}V)"],
        "control_signal_volts": signal,
        "safety_interlock_engaged": not safety,
        "calibration_offset": offset,
    }


def calculate_torque_requirements(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    load = float(inp.get("load_torque", 1.5))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_torque_requirements(load={load}Nm)"],
        "current_load_nm": load,
    }


def execute_mechanical_move(state: State) -> dict[str, Any]:
    signal = state.get("control_signal_volts", 0.0)
    load = state.get("current_load_nm", 1.0)
    interlock = state.get("safety_interlock_engaged", False)
    offset = state.get("calibration_offset", 0.0)

    # Simple actuation logic: if interlock is engaged, position is 0.
    # Otherwise position is proportional to signal/load with offset.
    if interlock:
        pos = 0.0
    else:
        raw_pos = (signal * 10.0) / max(0.1, load)
        pos = min(100.0, max(0.0, raw_pos + offset))

    return {
        "log": [f"{UNISPSC_CODE}:execute_mechanical_move(pos={pos:.1f}%)"],
        "actuation_position_pct": pos,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "position_pct": pos,
                "interlock_status": "ENGAGED" if interlock else "CLEAR",
                "load_detected_nm": load,
                "calibrated": True
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate_signal", evaluate_signal)
_g.add_node("calculate_torque_requirements", calculate_torque_requirements)
_g.add_node("execute_mechanical_move", execute_mechanical_move)

_g.add_edge(START, "evaluate_signal")
_g.add_edge("evaluate_signal", "calculate_torque_requirements")
_g.add_edge("calculate_torque_requirements", "execute_mechanical_move")
_g.add_edge("execute_mechanical_move", END)

graph = _g.compile()
