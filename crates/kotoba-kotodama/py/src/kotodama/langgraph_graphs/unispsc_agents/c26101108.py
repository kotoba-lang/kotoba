# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101108 — Motor (segment 26).

This bespoke implementation handles motor-specific state transitions including
topology verification, efficiency analysis, and final unit certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101108"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101108"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Motor lifecycle management
    nominal_voltage: int
    thermal_rating_verified: bool
    efficiency_ie_level: str
    inspection_passed: bool


def verify_motor_topology(state: State) -> dict[str, Any]:
    """Inspects input parameters to determine motor configuration."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 400)
    return {
        "log": [f"{UNISPSC_CODE}:verify_motor_topology"],
        "nominal_voltage": voltage,
        "thermal_rating_verified": True if voltage <= 600 else False,
    }


def analyze_efficiency(state: State) -> dict[str, Any]:
    """Calculates efficiency classification based on motor specs."""
    voltage = state.get("nominal_voltage", 0)
    # Simplified logic: higher voltage machines in this segment assumed IE4
    ie_level = "IE4" if voltage > 380 else "IE3"
    return {
        "log": [f"{UNISPSC_CODE}:analyze_efficiency"],
        "efficiency_ie_level": ie_level,
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Produces the final compliance result for the motor unit."""
    is_safe = state.get("thermal_rating_verified", False)
    ie_level = state.get("efficiency_ie_level", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "inspection_passed": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "compliance": {
                "voltage_safe": is_safe,
                "efficiency_class": ie_level,
            },
            "status": "APPROVED" if is_safe else "REJECTED",
        },
    }


_g = StateGraph(State)
_g.add_node("verify_topology", verify_motor_topology)
_g.add_node("analyze_efficiency", analyze_efficiency)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "verify_topology")
_g.add_edge("verify_topology", "analyze_efficiency")
_g.add_edge("analyze_efficiency", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
