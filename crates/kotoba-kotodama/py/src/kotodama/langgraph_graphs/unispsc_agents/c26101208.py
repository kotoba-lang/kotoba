# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101208 — Motor.

Bespoke graph logic for industrial motor verification and state management.
This agent handles motor specification validation, torque simulation, and
certification of efficiency parameters within segment 26.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101208"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101208"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_ac: int
    torque_rating_nm: float
    winding_integrity: bool
    efficiency_class: str


def validate_electrical_specs(state: State) -> dict[str, Any]:
    """Validates the input electrical requirements for the motor."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 480)
    # Basic validation: ensure voltage is within industrial standards
    integrity = voltage > 0 and voltage < 1000
    return {
        "log": [f"{UNISPSC_CODE}:validate_electrical_specs"],
        "voltage_ac": voltage,
        "winding_integrity": integrity,
    }


def simulate_load_performance(state: State) -> dict[str, Any]:
    """Simulates motor performance under rated load conditions."""
    voltage = state.get("voltage_ac", 0)
    # Calculate synthetic torque based on voltage for simulation
    torque = (voltage / 480.0) * 50.0 if voltage > 0 else 0.0

    # Assign efficiency class based on torque output stability
    eff = "IE3" if torque > 45.0 else "IE2"

    return {
        "log": [f"{UNISPSC_CODE}:simulate_load_performance"],
        "torque_rating_nm": round(torque, 2),
        "efficiency_class": eff,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Generates the final motor certification and result payload."""
    is_valid = state.get("winding_integrity", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_valid else "REJECTED",
            "metrics": {
                "voltage": state.get("voltage_ac"),
                "torque_nm": state.get("torque_rating_nm"),
                "efficiency": state.get("efficiency_class"),
            },
            "ok": is_valid,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_electrical_specs", validate_electrical_specs)
_g.add_node("simulate_load_performance", simulate_load_performance)
_g.add_node("emit_certification", emit_certification)

_g.add_edge(START, "validate_electrical_specs")
_g.add_edge("validate_electrical_specs", "simulate_load_performance")
_g.add_edge("simulate_load_performance", "emit_certification")
_g.add_edge("emit_certification", END)

graph = _g.compile()
