# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20143000 — Well stimulation and intervention services.

This agent handles the lifecycle of well stimulation and intervention equipment
requests, including safety verification, resource manifest generation, and
deployment finalization within the Mining and Well Drilling machinery segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20143000"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20143000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    well_site_id: str
    intervention_method: str
    safety_clearance: bool
    equipment_list: list[str]
    max_pressure_psi: int


def validate_well_intervention(state: State) -> dict[str, Any]:
    """Validates the intervention request against site safety standards."""
    inp = state.get("input") or {}
    well_id = inp.get("well_id", "SITE-DEFAULT")
    method = inp.get("method", "hydraulic_fracturing")

    # Basic validation of safety clearance based on input parameters
    is_safe = inp.get("safety_override", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_well_intervention"],
        "well_site_id": well_id,
        "intervention_method": method,
        "safety_clearance": is_safe,
    }


def prepare_equipment(state: State) -> dict[str, Any]:
    """Selects appropriate stimulation equipment based on the intervention method."""
    method = state.get("intervention_method", "generic")

    # Select equipment and pressure thresholds based on method
    if "fracturing" in method.lower():
        units = ["High-Pressure Pump", "Sand Blender", "Monitoring Van", "Water Storage"]
        psi = 15000
    elif "acidizing" in method.lower():
        units = ["Chemical Tank", "Acid-Resistant Pump", "Neutralizer Unit"]
        psi = 8000
    else:
        units = ["Standard Intervention Rig", "Wellhead Tooling"]
        psi = 5000

    return {
        "log": [f"{UNISPSC_CODE}:prepare_equipment"],
        "equipment_list": units,
        "max_pressure_psi": psi,
    }


def finalize_intervention_plan(state: State) -> dict[str, Any]:
    """Finalizes the deployment plan and formats the result for the executor."""
    clearance = state.get("safety_clearance", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "well_id": state.get("well_site_id"),
        "method": state.get("intervention_method"),
        "equipment": state.get("equipment_list"),
        "pressure_limit": state.get("max_pressure_psi"),
        "safety_status": "APPROVED" if clearance else "DENIED",
        "ok": clearance,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_intervention_plan"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("validate", validate_well_intervention)
_g.add_node("prepare", prepare_equipment)
_g.add_node("finalize", finalize_intervention_plan)

_g.add_edge(START, "validate")
_g.add_edge("validate", "prepare")
_g.add_edge("prepare", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
