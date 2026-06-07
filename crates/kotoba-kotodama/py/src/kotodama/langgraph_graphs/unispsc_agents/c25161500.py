# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25161500 — Vehicle (segment 25).

Bespoke graph logic for vehicle asset lifecycle management, registration
verification, and fleet metadata emission.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161500"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Vehicle
    vin: str
    vehicle_type: str
    registration_valid: bool
    maintenance_status: str


def inspect_registration(state: State) -> dict[str, Any]:
    """Validate vehicle identity and registration status."""
    inp = state.get("input") or {}
    vin = inp.get("vin", "NON-ID-VEHICLE")
    # Simulation: VINs starting with 'V' are pre-verified
    is_valid = vin.startswith("V")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_registration vin={vin} valid={is_valid}"],
        "vin": vin,
        "registration_valid": is_valid
    }


def verify_maintenance(state: State) -> dict[str, Any]:
    """Check maintenance logs based on vehicle type."""
    inp = state.get("input") or {}
    v_type = inp.get("type", "Standard")
    # Simulation: Default to nominal status for new records
    status = "nominal" if state.get("registration_valid") else "quarantined"

    return {
        "log": [f"{UNISPSC_CODE}:verify_maintenance type={v_type} status={status}"],
        "vehicle_type": v_type,
        "maintenance_status": status
    }


def emit_vehicle_record(state: State) -> dict[str, Any]:
    """Finalize the vehicle asset record for the registry."""
    is_ok = state.get("registration_valid", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_vehicle_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vin": state.get("vin"),
            "type": state.get("vehicle_type"),
            "status": state.get("maintenance_status"),
            "authorized": is_ok,
            "status_code": "ACTIVE" if is_ok else "PENDING_REGISTRATION"
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_registration", inspect_registration)
_g.add_node("verify_maintenance", verify_maintenance)
_g.add_node("emit_vehicle_record", emit_vehicle_record)

_g.add_edge(START, "inspect_registration")
_g.add_edge("inspect_registration", "verify_maintenance")
_g.add_edge("verify_maintenance", "emit_vehicle_record")
_g.add_edge("emit_vehicle_record", END)

graph = _g.compile()
