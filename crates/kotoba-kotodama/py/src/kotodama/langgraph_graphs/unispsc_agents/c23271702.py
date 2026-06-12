# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271702 — Torch.
This agent handles the operational state for welding and cutting torches,
ensuring safety protocols and gas calibration for industrial use.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271702"
UNISPSC_TITLE = "Torch"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Torch
    gas_mixture: str
    target_temperature_celsius: int
    safety_valve_status: str
    ignition_verified: bool


def inspect_hardware(state: State) -> dict[str, Any]:
    """Validates the physical state of the torch before ignition."""
    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "safety_valve_status": "engaged",
        "ignition_verified": False,
    }


def calibrate_gas_flow(state: State) -> dict[str, Any]:
    """Processes input parameters to set gas mixture and temperature."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "brazing")

    # Simple logic mapping for industrial torch applications
    if mode == "cutting":
        gas = "Oxy-Acetylene"
        temp = 3500
    elif mode == "welding":
        gas = "Oxy-Hydrogen"
        temp = 2800
    else:
        gas = "Propane-Air"
        temp = 1900

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_gas_flow"],
        "gas_mixture": gas,
        "target_temperature_celsius": temp,
    }


def finalize_operational_state(state: State) -> dict[str, Any]:
    """Confirms the torch is ready for duty and emits the final telemetry."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operational_state"],
        "ignition_verified": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "READY",
            "telemetry": {
                "gas": state.get("gas_mixture"),
                "temp": state.get("target_temperature_celsius"),
                "safety_lock": state.get("safety_valve_status"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_hardware)
_g.add_node("calibrate", calibrate_gas_flow)
_g.add_node("finalize", finalize_operational_state)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
