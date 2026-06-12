# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242001 — Machine (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242001"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Machine-specific domain state fields
    machine_id: str
    safety_status: str
    calibration_drift: float
    operational_mode: str


def check_safety_protocols(state: State) -> dict[str, Any]:
    """Validates the safety interlocks and current operational constraints."""
    inp = state.get("input") or {}
    m_id = inp.get("machine_id", "GEN-MACH-01")

    # Logic: Safety is verified if diagnostic_bypass is not requested
    is_safe = inp.get("diagnostic_bypass") is not True
    status = "READY" if is_safe else "LOCKED"

    return {
        "log": [f"{UNISPSC_CODE}:check_safety_protocols -> {status}"],
        "machine_id": m_id,
        "safety_status": status,
        "operational_mode": "IDLE"
    }


def calibrate_and_prime(state: State) -> dict[str, Any]:
    """Simulates machine calibration and pressure priming."""
    if state.get("safety_status") != "READY":
        return {
            "log": [f"{UNISPSC_CODE}:calibrate_and_prime: skipped - safety lock"],
            "operational_mode": "FAULT"
        }

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_and_prime: precision_offset=0.002mm"],
        "calibration_drift": 0.002,
        "operational_mode": "ACTIVE"
    }


def execute_production_cycle(state: State) -> dict[str, Any]:
    """Transitions state to completed cycle and generates results."""
    mode = state.get("operational_mode")
    success = mode == "ACTIVE"

    return {
        "log": [f"{UNISPSC_CODE}:execute_production_cycle: success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "machine_id": state.get("machine_id"),
            "operational_result": "COMPLETED" if success else "ABORTED",
            "telemetry": {
                "drift": state.get("calibration_drift", 0.0),
                "mode": mode
            }
        }
    }


_g = StateGraph(State)
_g.add_node("check_safety_protocols", check_safety_protocols)
_g.add_node("calibrate_and_prime", calibrate_and_prime)
_g.add_node("execute_production_cycle", execute_production_cycle)

_g.add_edge(START, "check_safety_protocols")
_g.add_edge("check_safety_protocols", "calibrate_and_prime")
_g.add_edge("calibrate_and_prime", "execute_production_cycle")
_g.add_edge("execute_production_cycle", END)

graph = _g.compile()
