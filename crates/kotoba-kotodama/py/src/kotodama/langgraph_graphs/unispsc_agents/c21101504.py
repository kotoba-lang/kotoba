# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101504 — Haying Equipment.

This module implements a bespoke state machine for haying equipment operation,
including hydraulic system validation, safety sensor verification, and
operational status reporting for segment 21.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101504"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    bale_type: str
    hydraulic_pressure_psi: float
    safety_interlock_active: bool
    moisture_content: float
    is_operational: bool


def check_hydraulics(state: State) -> dict[str, Any]:
    """Validates the hydraulic pressure for haying machinery."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 2500.0))
    b_type = inp.get("bale_type", "round")

    return {
        "log": [f"{UNISPSC_CODE}:check_hydraulics:psi={pressure}"],
        "hydraulic_pressure_psi": pressure,
        "bale_type": b_type,
    }


def verify_safety_sensors(state: State) -> dict[str, Any]:
    """Ensures safety interlocks and moisture sensors are within nominal ranges."""
    pressure = state.get("hydraulic_pressure_psi", 0.0)
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 15.0))

    # Nominally operational if pressure is above 1800 PSI
    interlock = pressure > 1800.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_sensors:active={interlock}"],
        "safety_interlock_active": interlock,
        "moisture_content": moisture,
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Finalizes the equipment status and prepares the actor result."""
    safe = state.get("safety_interlock_active", False)
    moisture = state.get("moisture_content", 0.0)
    bale = state.get("bale_type", "N/A")

    # Ready for field use if safe and moisture is below 20%
    ready = safe and moisture < 20.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation:ready={ready}"],
        "is_operational": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "operational" if ready else "maintenance_required",
            "telemetry": {
                "bale_format": bale,
                "moisture_pct": moisture,
                "safe_state": safe
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("check_hydraulics", check_hydraulics)
_g.add_node("verify_safety_sensors", verify_safety_sensors)
_g.add_node("finalize_operation", finalize_operation)

_g.add_edge(START, "check_hydraulics")
_g.add_edge("check_hydraulics", "verify_safety_sensors")
_g.add_edge("verify_safety_sensors", "finalize_operation")
_g.add_edge("finalize_operation", END)

graph = _g.compile()
