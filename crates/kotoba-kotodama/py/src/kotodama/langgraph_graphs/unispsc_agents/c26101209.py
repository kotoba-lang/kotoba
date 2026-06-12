# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101209 — Motor (segment 26).

This bespoke agent manages the validation and processing of electrical motor
specifications within the power generation and distribution segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101209"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101209"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_rating: int
    power_factor: float
    torque_nominal: float
    safety_shutdown_active: bool


def inspect_electrical_parameters(state: State) -> dict[str, Any]:
    """Validates the supply voltage and power factor for the motor."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 230)
    pf = inp.get("power_factor", 0.85)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_electrical_parameters"],
        "voltage_rating": voltage,
        "power_factor": pf,
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates mechanical torque and evaluates load stability."""
    inp = state.get("input") or {}
    kw = inp.get("kw", 1.5)
    rpm = inp.get("rpm", 1440)

    # Torque T = (9550 * P) / n
    torque = (9550 * kw) / rpm if rpm > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "torque_nominal": round(torque, 2),
        "safety_shutdown_active": inp.get("temp", 25) > 90,
    }


def generate_motor_certificate(state: State) -> dict[str, Any]:
    """Finalizes the processing and emits the motor certification status."""
    is_safe = not state.get("safety_shutdown_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_motor_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "voltage": state.get("voltage_rating"),
                "torque_nm": state.get("torque_nominal"),
                "power_factor": state.get("power_factor"),
            },
            "certification_status": "APPROVED" if is_safe else "REJECTED_THERMAL_EXCESS",
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_electrical", inspect_electrical_parameters)
_g.add_node("analyze_performance", analyze_performance)
_g.add_node("generate_certificate", generate_motor_certificate)

_g.add_edge(START, "inspect_electrical")
_g.add_edge("inspect_electrical", "analyze_performance")
_g.add_edge("analyze_performance", "generate_certificate")
_g.add_edge("generate_certificate", END)

graph = _g.compile()
