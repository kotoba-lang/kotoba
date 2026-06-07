# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101500 — Vehicle (segment 25).

Bespoke graph logic for vehicle asset lifecycle management, including
specification inspection, registration verification, and record finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101500"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific vehicle state
    vin: str
    vehicle_class: str
    registration_valid: bool
    inspection_notes: str


def inspect_vehicle_specs(state: State) -> dict[str, Any]:
    """Node to parse vehicle specifications from input."""
    inp = state.get("input") or {}
    vin = inp.get("vin", "PENDING_ASSIGNMENT")
    v_class = inp.get("class", "unclassified")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle_specs:vin={vin}"],
        "vin": vin,
        "vehicle_class": v_class,
    }


def verify_registration(state: State) -> dict[str, Any]:
    """Node to verify the legality and registration status of the vehicle."""
    vin = state.get("vin")
    is_valid = vin is not None and len(vin) >= 8 and vin != "PENDING_ASSIGNMENT"
    status_msg = "PASSED" if is_valid else "FAILED_IDENTIFICATION"
    return {
        "log": [f"{UNISPSC_CODE}:verify_registration:{status_msg}"],
        "registration_valid": is_valid,
        "inspection_notes": f"Safety verification status: {status_msg}",
    }


def finalize_vehicle_record(state: State) -> dict[str, Any]:
    """Node to compile the final verified vehicle asset record."""
    is_ok = state.get("registration_valid", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_vehicle_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset_id": state.get("vin"),
            "class": state.get("vehicle_class"),
            "compliance": state.get("inspection_notes"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_vehicle_specs)
_g.add_node("verify", verify_registration)
_g.add_node("finalize", finalize_vehicle_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
