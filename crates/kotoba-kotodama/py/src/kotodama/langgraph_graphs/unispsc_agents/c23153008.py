# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153008"
UNISPSC_TITLE = "Jig"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153008"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Jig (Industrial Process Machinery)
    jig_specification: dict[str, Any]
    calibration_status: str
    clamping_force_newtons: float
    material_compatibility: list[str]
    safety_check_passed: bool


def configure_jig(state: State) -> dict[str, Any]:
    """Initializes the jig configuration based on input parameters."""
    inp = state.get("input") or {}
    spec = {
        "type": inp.get("type", "machining_jig"),
        "tolerance_class": inp.get("tolerance", "IT7"),
        "base_material": inp.get("material", "hardened_steel"),
    }
    return {
        "log": [f"{UNISPSC_CODE}:configure_jig"],
        "jig_specification": spec,
        "calibration_status": "pending",
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates clamping force and verifies material compatibility."""
    spec = state.get("jig_specification") or {}
    # Simulated engineering calculations
    force = 1500.0 if spec.get("type") == "machining_jig" else 500.0
    compat = ["aluminum", "steel", "brass"]
    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "clamping_force_newtons": force,
        "material_compatibility": compat,
        "calibration_status": "calibrated",
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Final safety and compliance check before operation."""
    force = state.get("clamping_force_newtons", 0)
    status = state.get("calibration_status")
    # A jig is safe if it is calibrated and has sufficient clamping force
    is_safe = status == "calibrated" and force >= 400.0
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit"],
        "safety_check_passed": is_safe,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Compiles the final state into the result dictionary."""
    is_safe = state.get("safety_check_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operational_status": "authorized" if is_safe else "inhibited",
            "specs": state.get("jig_specification"),
            "metrics": {
                "clamping_force": state.get("clamping_force_newtons"),
                "calibrated": state.get("calibration_status") == "calibrated"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_jig)
_g.add_node("analyze", analyze_performance)
_g.add_node("audit", perform_safety_audit)
_g.add_node("emit", emit_result)

_g.add_edge(START, "configure")
_g.add_edge("configure", "analyze")
_g.add_edge("analyze", "audit")
_g.add_edge("audit", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
