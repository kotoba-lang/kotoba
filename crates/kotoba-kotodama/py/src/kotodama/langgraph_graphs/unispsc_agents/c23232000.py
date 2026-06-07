# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23232000 — Lathe.
Bespoke implementation for machining tool path validation and spindle control simulation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23232000"
UNISPSC_TITLE = "Lathe"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23232000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lathe operations
    spindle_speed_rpm: int
    feed_rate_mm_rev: float
    material_type: str
    safety_interlock_engaged: bool
    tolerance_check_passed: bool


def validate_setup(state: State) -> dict[str, Any]:
    """Validates the lathe configuration and safety protocols."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")

    # Lathes require safety interlocks for rotation
    safety_engaged = inp.get("safety_override") is not True

    return {
        "log": [f"{UNISPSC_CODE}:validate_setup -> safety_engaged={safety_engaged}"],
        "material_type": material,
        "safety_interlock_engaged": safety_engaged,
    }


def compute_machining_parameters(state: State) -> dict[str, Any]:
    """Calculates spindle speed and feed rate based on material hardness."""
    material = state.get("material_type", "carbon_steel")

    # Simple logic for tool speed calculation
    if material == "aluminum":
        rpm = 1200
        feed = 0.25
    elif material == "titanium":
        rpm = 400
        feed = 0.08
    else:
        rpm = 800
        feed = 0.15

    return {
        "log": [f"{UNISPSC_CODE}:compute_machining_parameters -> rpm={rpm}"],
        "spindle_speed_rpm": rpm,
        "feed_rate_mm_rev": feed,
        "tolerance_check_passed": state.get("safety_interlock_engaged", False),
    }


def finalize_machining_cycle(state: State) -> dict[str, Any]:
    """Emits the final machining report and status."""
    is_ok = state.get("tolerance_check_passed", False) and state.get("safety_interlock_engaged", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_machining_cycle -> ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machining_status": "completed" if is_ok else "failed_safety_check",
            "parameters": {
                "rpm": state.get("spindle_speed_rpm"),
                "feed": state.get("feed_rate_mm_rev"),
                "material": state.get("material_type"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_setup)
_g.add_node("compute", compute_machining_parameters)
_g.add_node("finalize", finalize_machining_cycle)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
