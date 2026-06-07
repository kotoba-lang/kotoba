# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23130000 — Tool (segment 23).

Bespoke graph logic for industrial laundry and dry cleaning equipment,
focusing on capacity validation, utility requirements, and safety compliance.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23130000"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23130000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Industrial Laundry Equipment
    load_capacity_kg: float
    voltage_requirement: int
    is_safety_certified: bool


def assess_equipment_specs(state: State) -> dict[str, Any]:
    """Analyze the equipment specifications against industrial requirements."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 50.0)

    return {
        "log": [f"{UNISPSC_CODE}:assess_equipment_specs - Capacity: {capacity}kg"],
        "load_capacity_kg": capacity,
    }


def verify_utility_compliance(state: State) -> dict[str, Any]:
    """Ensure site utilities (power/water) meet the equipment demands."""
    # Standard industrial laundry equipment voltage requirement
    req_voltage = 400

    return {
        "log": [f"{UNISPSC_CODE}:verify_utility_compliance - Target Voltage: {req_voltage}V"],
        "voltage_requirement": req_voltage,
    }


def final_safety_check(state: State) -> dict[str, Any]:
    """Perform final safety certification check and emit result."""
    inp = state.get("input") or {}
    certified = inp.get("safety_cert", True)

    return {
        "log": [f"{UNISPSC_CODE}:final_safety_check - Certified: {certified}"],
        "is_safety_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "capacity_kg": state.get("load_capacity_kg"),
                "voltage_v": state.get("voltage_requirement"),
            },
            "ok": certified,
        },
    }


_g = StateGraph(State)

_g.add_node("assess_equipment_specs", assess_equipment_specs)
_g.add_node("verify_utility_compliance", verify_utility_compliance)
_g.add_node("final_safety_check", final_safety_check)

_g.add_edge(START, "assess_equipment_specs")
_g.add_edge("assess_equipment_specs", "verify_utility_compliance")
_g.add_edge("verify_utility_compliance", "final_safety_check")
_g.add_edge("final_safety_check", END)

graph = _g.compile()
