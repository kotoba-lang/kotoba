# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121412 — Motor (segment 20).

Bespoke graph logic for motor performance validation and certification.
This agent handles the lifecycle of motor unit verification, including
specification validation, simulated bench testing, and efficiency certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121412"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121412"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Motor units
    specs_verified: bool
    operating_status: str
    telemetry_data: dict[str, Any]
    efficiency_rating: float


def validate_motor_specs(state: State) -> dict[str, Any]:
    """Checks the input for required electrical and mechanical parameters."""
    inp = state.get("input") or {}
    power_kw = inp.get("power_kw")
    voltage_v = inp.get("voltage_v")

    # Simple validation logic for motor specifications
    is_valid = isinstance(power_kw, (int, float)) and isinstance(voltage_v, (int, float))
    return {
        "log": [f"{UNISPSC_CODE}:validate_motor_specs"],
        "specs_verified": is_valid,
        "operating_status": "validated" if is_valid else "invalid_input"
    }


def perform_bench_test(state: State) -> dict[str, Any]:
    """Simulates a standardized load test for the motor unit."""
    if not state.get("specs_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:perform_bench_test:aborted"],
            "operating_status": "failed_verification"
        }

    # Simulated telemetry metrics captured during the test phase
    telemetry = {
        "rpm": 1750,
        "torque_nm": 45.2,
        "winding_temp_c": 62.0,
        "noise_level_db": 68.5
    }
    efficiency = 0.94

    return {
        "log": [f"{UNISPSC_CODE}:perform_bench_test:completed"],
        "telemetry_data": telemetry,
        "efficiency_rating": efficiency,
        "operating_status": "tested"
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Generates the final certification status and result metadata."""
    status = state.get("operating_status")
    efficiency = state.get("efficiency_rating", 0.0)

    # Certification criteria: successful test and high efficiency
    is_certified = status == "tested" and efficiency > 0.85

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_certified,
            "metrics": state.get("telemetry_data"),
            "efficiency": efficiency,
            "ok": is_certified
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_motor_specs)
_g.add_node("test", perform_bench_test)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
