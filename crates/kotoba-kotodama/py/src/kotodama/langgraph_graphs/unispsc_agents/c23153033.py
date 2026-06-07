# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153033 — Weld.
Bespoke logic for welding process state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153033"
UNISPSC_TITLE = "Weld"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153033"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Welding operation state
    weld_type: str
    material_thickness: float
    voltage_setpoint: int
    shielding_gas_active: bool
    operation_status: str


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the input welding parameters and determines machine settings."""
    inp = state.get("input") or {}
    w_type = str(inp.get("weld_type", "MIG"))
    thickness = float(inp.get("material_thickness", 2.0))

    # Calculate voltage based on material thickness (pseudo-logic)
    voltage = int(thickness * 12) + 15
    gas_req = w_type.upper() in ["MIG", "TIG", "MAG"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters: type={w_type}, thick={thickness}mm"],
        "weld_type": w_type,
        "material_thickness": thickness,
        "voltage_setpoint": voltage,
        "shielding_gas_active": gas_req
    }


def perform_welding_cycle(state: State) -> dict[str, Any]:
    """Simulates the execution of the welding cycle."""
    v = state.get("voltage_setpoint", 0)
    gas = state.get("shielding_gas_active", False)

    # Process logic: check if parameters are within safe operating bounds
    if v > 100:
        status = "ERROR_OVER_VOLTAGE"
    elif gas and v < 20:
        status = "ERROR_INSUFFICIENT_ARC_STABILITY"
    else:
        status = "COMPLETED_SUCCESSFULLY"

    return {
        "log": [f"{UNISPSC_CODE}:perform_welding_cycle: {status}"],
        "operation_status": status
    }


def generate_welding_report(state: State) -> dict[str, Any]:
    """Compiles the final state into a standardized result dictionary."""
    status = state.get("operation_status", "INCOMPLETE")
    return {
        "log": [f"{UNISPSC_CODE}:generate_welding_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": status == "COMPLETED_SUCCESSFULLY",
            "telemetry": {
                "weld_type": state.get("weld_type"),
                "voltage": state.get("voltage_setpoint"),
                "status_code": status
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("execute", perform_welding_cycle)
_g.add_node("report", generate_welding_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "execute")
_g.add_edge("execute", "report")
_g.add_edge("report", END)

graph = _g.compile()
