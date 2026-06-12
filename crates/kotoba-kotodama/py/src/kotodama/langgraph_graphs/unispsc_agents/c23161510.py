# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161510 — Compressor (segment 23).

Bespoke logic for industrial compressor lifecycle management, including
pressure setpoint calibration, flow rate optimization, and safety interlock
verification for pneumatic systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161510"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Compressor operations
    target_pressure_psi: float
    max_flow_rate_cfm: float
    power_source_type: str
    safety_interlock_active: bool
    maintenance_interval_hours: int


def configure_compressor(state: State) -> dict[str, Any]:
    """Initializes the compressor configuration based on pneumatic requirements."""
    inp = state.get("input") or {}
    pressure = float(inp.get("target_pressure", 125.0))
    power = inp.get("power_source", "electric_3phase")
    return {
        "log": [f"{UNISPSC_CODE}:configure_compressor"],
        "target_pressure_psi": pressure,
        "power_source_type": power,
    }


def calibrate_pressure_system(state: State) -> dict[str, Any]:
    """Calculates flow rates and maintenance parameters for the pressure setpoint."""
    pressure = state.get("target_pressure_psi", 0.0)
    # Heuristic: Maintenance interval decreases with higher pressure demands
    interval = 2000 if pressure < 150.0 else 1200
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_pressure_system"],
        "max_flow_rate_cfm": 50.0 + (pressure * 0.1),
        "maintenance_interval_hours": interval,
    }


def verify_compressor_safety(state: State) -> dict[str, Any]:
    """Ensures pneumatic safety interlocks are verified for high-pressure discharge."""
    pressure = state.get("target_pressure_psi", 0.0)
    # Automatic interlock activation for high-pressure configurations
    interlock = True if pressure > 100.0 else False
    return {
        "log": [f"{UNISPSC_CODE}:verify_compressor_safety"],
        "safety_interlock_active": interlock,
    }


def finalize_compressor_state(state: State) -> dict[str, Any]:
    """Aggregates the operational state into the final compressor actor response."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_compressor_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ready_to_pressurize",
            "config": {
                "pressure_psi": state.get("target_pressure_psi"),
                "flow_cfm": state.get("max_flow_rate_cfm"),
                "power": state.get("power_source_type"),
            },
            "safety": {
                "interlock_engaged": state.get("safety_interlock_active"),
                "next_maintenance_h": state.get("maintenance_interval_hours"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_compressor)
_g.add_node("calibrate", calibrate_pressure_system)
_g.add_node("safety_check", verify_compressor_safety)
_g.add_node("finalize", finalize_compressor_state)

_g.add_edge(START, "configure")
_g.add_edge("configure", "calibrate")
_g.add_edge("calibrate", "safety_check")
_g.add_edge("safety_check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
