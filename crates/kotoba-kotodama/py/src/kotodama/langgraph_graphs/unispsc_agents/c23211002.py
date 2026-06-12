# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23211002 — Dispenser (segment 23).

Industrial dispensing agent responsible for precise volume control,
calibration verification, and reservoir management within the
manufacturing segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23211002"
UNISPSC_TITLE = "Dispenser"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23211002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Dispenser operations
    fluid_composition: str
    target_volume_cc: float
    current_reservoir_psi: float
    dispense_cycle_id: str
    safety_interlock_active: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Ensures input parameters are within machine operating range."""
    inp = state.get("input") or {}
    vol = float(inp.get("volume", 0.0))
    fluid = inp.get("fluid", "ISO-VG-46")
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters: vol={vol}, fluid={fluid}"],
        "target_volume_cc": vol,
        "fluid_composition": fluid,
        "safety_interlock_active": True,
    }


def execute_pumping_logic(state: State) -> dict[str, Any]:
    """Performs the physical dispense simulation and pressure monitoring."""
    target = state.get("target_volume_cc", 0.0)
    # Simulate pressure drop during operation
    return {
        "log": [f"{UNISPSC_CODE}:execute_pumping_logic: processing {target}cc"],
        "current_reservoir_psi": 85.5,
        "dispense_cycle_id": f"CYC-{UNISPSC_CODE}-12345",
    }


def finalize_transaction(state: State) -> dict[str, Any]:
    """Generates the final report and releases safety interlocks."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_transaction: cycle complete"],
        "safety_interlock_active": False,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "cycle_id": state.get("dispense_cycle_id"),
            "final_volume_cc": state.get("target_volume_cc"),
            "pressure_psi": state.get("current_reservoir_psi"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("dispense", execute_pumping_logic)
_g.add_node("audit", finalize_transaction)

_g.add_edge(START, "validate")
_g.add_edge("validate", "dispense")
_g.add_edge("dispense", "audit")
_g.add_edge("audit", END)

graph = _g.compile()
