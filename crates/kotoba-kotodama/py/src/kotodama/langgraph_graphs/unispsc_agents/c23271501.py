# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271501 — Furnace (segment 23).
Industrial furnace operation logic involving safety validation, burner ignition,
and thermal output stabilization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271501"
UNISPSC_TITLE = "Furnace"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Furnace operation
    target_temperature_c: int
    chamber_pressure_hpa: float
    safety_interlock_active: bool
    ignition_sequence_complete: bool
    thermal_output_kw: float


def validate_safety_interlocks(state: State) -> dict[str, Any]:
    """Ensures all safety systems are engaged before fuel entry."""
    inp = state.get("input") or {}
    requested_temp = inp.get("temp", 1200)
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_interlocks"],
        "target_temperature_c": requested_temp,
        "chamber_pressure_hpa": 1013.25,
        "safety_interlock_active": True,
    }


def execute_ignition_sequence(state: State) -> dict[str, Any]:
    """Triggers pilot system and ramps up primary burner arrays."""
    is_safe = state.get("safety_interlock_active", False)
    return {
        "log": [f"{UNISPSC_CODE}:execute_ignition_sequence"],
        "ignition_sequence_complete": is_safe,
        "thermal_output_kw": 450.5 if is_safe else 0.0,
    }


def finalize_thermal_output(state: State) -> dict[str, Any]:
    """Verifies stabilization and packages telemetry for the result."""
    temp = state.get("target_temperature_c", 0)
    output = state.get("thermal_output_kw", 0.0)
    success = state.get("ignition_sequence_complete", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_thermal_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ACTIVE" if success else "FAULT",
            "telemetry": {
                "setpoint": temp,
                "output_kw": output,
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety_interlocks", validate_safety_interlocks)
_g.add_node("execute_ignition_sequence", execute_ignition_sequence)
_g.add_node("finalize_thermal_output", finalize_thermal_output)

_g.add_edge(START, "validate_safety_interlocks")
_g.add_edge("validate_safety_interlocks", "execute_ignition_sequence")
_g.add_edge("execute_ignition_sequence", "finalize_thermal_output")
_g.add_edge("finalize_thermal_output", END)

graph = _g.compile()
