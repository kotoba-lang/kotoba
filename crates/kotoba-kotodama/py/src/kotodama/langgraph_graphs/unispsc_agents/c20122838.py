# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122838"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122838"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Actuator
    target_position: float
    current_position: float
    actuation_force: float
    is_calibrated: bool
    duty_cycle: float


def validate_signal(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    current = float(inp.get("current", 0.0))
    calibrated = bool(inp.get("calibrated", True))

    return {
        "log": [f"{UNISPSC_CODE}:validate_signal"],
        "target_position": target,
        "current_position": current,
        "is_calibrated": calibrated,
    }


def compute_actuation(state: State) -> dict[str, Any]:
    target = state.get("target_position", 0.0)
    current = state.get("current_position", 0.0)

    displacement = target - current
    # Simple proportional control simulation
    force = displacement * 50.0
    duty = min(1.0, max(0.0, abs(displacement) / 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:compute_actuation"],
        "actuation_force": force,
        "duty_cycle": duty,
    }


def apply_control(state: State) -> dict[str, Any]:
    force = state.get("actuation_force", 0.0)
    duty = state.get("duty_cycle", 0.0)
    calibrated = state.get("is_calibrated", False)

    status_ok = calibrated and (0.0 <= duty <= 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:apply_control"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "applied_force_nm": force,
            "duty_cycle_pct": duty * 100.0,
            "system_status": "operational" if status_ok else "degraded",
            "ok": status_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_signal", validate_signal)
_g.add_node("compute_actuation", compute_actuation)
_g.add_node("apply_control", apply_control)

_g.add_edge(START, "validate_signal")
_g.add_edge("validate_signal", "compute_actuation")
_g.add_edge("compute_actuation", "apply_control")
_g.add_edge("apply_control", END)

graph = _g.compile()
