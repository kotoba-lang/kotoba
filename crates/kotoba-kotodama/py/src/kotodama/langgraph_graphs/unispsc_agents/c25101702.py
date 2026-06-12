# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101702 — Vehicle (segment 25).

Bespoke graph logic for vehicle state management, focusing on VIN validation,
classification assessment, and registration status tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101702"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Vehicle
    vin: str
    vehicle_class: str
    registration_status: str
    inspection_passed: bool
    odometer_reading: int


def validate_vehicle(state: State) -> dict[str, Any]:
    """Validates the vehicle identity and basic safety status."""
    inp = state.get("input") or {}
    vin = str(inp.get("vin", "PENDING")).upper()
    # Simple VIN length validation for logic flow
    is_valid = len(vin) == 17

    return {
        "log": [f"{UNISPSC_CODE}:validate_vehicle"],
        "vin": vin,
        "inspection_passed": is_valid,
        "odometer_reading": int(inp.get("odometer", 0))
    }


def classify_vehicle(state: State) -> dict[str, Any]:
    """Determines the vehicle classification based on input specs."""
    inp = state.get("input") or {}
    weight = inp.get("gross_weight", 0)

    # Logic to distinguish between passenger and commercial
    if weight > 10000:
        v_class = "Heavy Commercial"
    elif weight > 4000:
        v_class = "Light Commercial"
    else:
        v_class = "Passenger"

    return {
        "log": [f"{UNISPSC_CODE}:classify_vehicle"],
        "vehicle_class": v_class
    }


def finalize_registration(state: State) -> dict[str, Any]:
    """Determines registration eligibility and emits final state."""
    is_safe = state.get("inspection_passed", False)
    v_class = state.get("vehicle_class", "Unknown")

    status = "Active" if is_safe else "Suspended"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_registration"],
        "registration_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vehicle_data": {
                "vin": state.get("vin"),
                "class": v_class,
                "status": status,
                "odometer": state.get("odometer_reading")
            },
            "ok": is_safe
        }
    }


_g = StateGraph(State)

_g.add_node("validate_vehicle", validate_vehicle)
_g.add_node("classify_vehicle", classify_vehicle)
_g.add_node("finalize_registration", finalize_registration)

_g.add_edge(START, "validate_vehicle")
_g.add_edge("validate_vehicle", "classify_vehicle")
_g.add_edge("classify_vehicle", "finalize_registration")
_g.add_edge("finalize_registration", END)

graph = _g.compile()
