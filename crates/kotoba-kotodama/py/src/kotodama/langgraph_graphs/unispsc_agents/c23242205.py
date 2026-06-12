# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242205 — Gear Machine (segment 23).
Bespoke logic for gear manufacturing machine control and quality verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242205"
UNISPSC_TITLE = "Gear Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242205"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for gear manufacturing
    gear_specifications: dict[str, Any]
    machine_state: str
    safety_check_verified: bool
    quality_metric: float
    production_passed: bool


def validate_setup(state: State) -> dict[str, Any]:
    """Validates the gear machine setup and safety parameters."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {"type": "spur", "teeth": 32, "pressure_angle": 20.0})
    safe = inp.get("safety_verified", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_setup"],
        "gear_specifications": specs,
        "machine_state": "ready" if safe else "blocked",
        "safety_check_verified": safe
    }


def execute_hobbing(state: State) -> dict[str, Any]:
    """Simulates the gear hobbing/machining process."""
    if not state.get("safety_check_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:hobbing_prevented_by_safety"],
            "machine_state": "safety_lockout"
        }

    g_type = state.get("gear_specifications", {}).get("type", "standard")
    return {
        "log": [f"{UNISPSC_CODE}:executing_hobbing_for_{g_type}_gear"],
        "machine_state": "machining_complete",
        "quality_metric": 0.98
    }


def quality_control(state: State) -> dict[str, Any]:
    """Performs dimensional inspection and surface analysis."""
    metric = state.get("quality_metric", 0.0)
    passed = metric >= 0.95

    return {
        "log": [f"{UNISPSC_CODE}:quality_control_score_{metric}"],
        "machine_state": "inspected" if passed else "rejected",
        "production_passed": passed
    }


def finalize_output(state: State) -> dict[str, Any]:
    """Compiles the final machine state and production data."""
    is_ok = state.get("production_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "outcome": "success" if is_ok else "failure",
            "telemetry": {
                "final_state": state.get("machine_state"),
                "specs": state.get("gear_specifications")
            }
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_setup)
_g.add_node("machining", execute_hobbing)
_g.add_node("quality", quality_control)
_g.add_node("finalize", finalize_output)

_g.add_edge(START, "validate")
_g.add_edge("validate", "machining")
_g.add_edge("machining", "quality")
_g.add_edge("quality", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
