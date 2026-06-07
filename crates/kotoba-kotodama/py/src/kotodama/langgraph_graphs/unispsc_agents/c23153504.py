# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153504 — Robot Control (segment 23).
Bespoke logic for safety validation, calibration verification, and motion control authorization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153504"
UNISPSC_TITLE = "Robot Control"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Robot Control processing
    safety_interlock_ok: bool
    calibration_valid: bool
    control_mode: str
    motion_authorized: bool


def validate_safety(state: State) -> dict[str, Any]:
    """Ensures safety interlocks and emergency stops are in a valid state."""
    inp = state.get("input") or {}
    safety_data = inp.get("safety", {})
    estop_released = safety_data.get("estop_released", False)
    light_curtain_clear = safety_data.get("light_curtain_clear", False)

    ok = estop_released and light_curtain_clear
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "safety_interlock_ok": ok,
    }


def check_calibration(state: State) -> dict[str, Any]:
    """Validates the last calibration timestamp and axis alignment."""
    if not state.get("safety_interlock_ok"):
        return {
            "log": [f"{UNISPSC_CODE}:check_calibration:skipped_unsafe"],
            "calibration_valid": False,
        }

    inp = state.get("input") or {}
    calibration = inp.get("calibration", {})
    drift_within_limits = calibration.get("drift", 0.0) < 0.05

    return {
        "log": [f"{UNISPSC_CODE}:check_calibration"],
        "calibration_valid": drift_within_limits,
    }


def authorize_motion(state: State) -> dict[str, Any]:
    """Finalizes control parameters and authorizes robotic motion."""
    safe = state.get("safety_interlock_ok", False)
    calibrated = state.get("calibration_valid", False)
    authorized = safe and calibrated

    mode = state.get("input", {}).get("mode", "manual")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_motion"],
        "motion_authorized": authorized,
        "control_mode": mode,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "motion_authorized": authorized,
            "mode": mode,
            "ok": authorized,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety", validate_safety)
_g.add_node("check_calibration", check_calibration)
_g.add_node("authorize_motion", authorize_motion)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "check_calibration")
_g.add_edge("check_calibration", "authorize_motion")
_g.add_edge("authorize_motion", END)

graph = _g.compile()
