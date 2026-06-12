# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201902 — Ejection System (segment 25).

Bespoke logic for managing vehicle ejection system state, ensuring safety
interlocks, pressure calibration, and deployment sequence verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201902"
UNISPSC_TITLE = "Ejection System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state
    pressure_psi: int
    safety_lock_active: bool
    ejection_force_kn: float
    sequence_ready: bool


def validate_safety(state: State) -> dict[str, Any]:
    """Inspects system pressure and safety interlocks."""
    inp = state.get("input") or {}
    req_pressure = inp.get("required_pressure", 3000)
    current_pressure = inp.get("current_pressure", 2950)

    # System is safe to arm only if pressure is within 10% of target
    is_safe = abs(current_pressure - req_pressure) / req_pressure < 0.1

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety: pressure={current_pressure}psi, safe={is_safe}"],
        "pressure_psi": current_pressure,
        "safety_lock_active": not is_safe,
    }


def calibrate_force(state: State) -> dict[str, Any]:
    """Determines ejection force based on payload weight."""
    inp = state.get("input") or {}
    payload_kg = inp.get("payload_kg", 85.0)

    # Calculation: 0.15 kN per kg of payload + base force
    force = (payload_kg * 0.15) + 12.0
    ready = not state.get("safety_lock_active", True)

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_force: force={force:.2f}kN, ready={ready}"],
        "ejection_force_kn": force,
        "sequence_ready": ready,
    }


def finalize_deployment(state: State) -> dict[str, Any]:
    """Finalizes the ejection parameters for the executor."""
    is_ready = state.get("sequence_ready", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "deployed": is_ready,
        "telemetry": {
            "force_kn": state.get("ejection_force_kn"),
            "pressure": state.get("pressure_psi"),
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_deployment: success={is_ready}"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("validate_safety", validate_safety)
_g.add_node("calibrate_force", calibrate_force)
_g.add_node("finalize_deployment", finalize_deployment)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "calibrate_force")
_g.add_edge("calibrate_force", "finalize_deployment")
_g.add_edge("finalize_deployment", END)

graph = _g.compile()
