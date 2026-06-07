# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23201201 — Vehicle (segment 23).

Bespoke graph logic for validating vehicle assets, processing real-time telemetry,
and managing fleet allocation. This implementation handles vehicle identification
(VIN) verification and maintenance status checking.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201201"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Vehicle
    vin_verified: bool
    maintenance_status: str
    fleet_id: str
    telemetry_active: bool


def validate_identity(state: State) -> dict[str, Any]:
    """Verify VIN format and register the vehicle in the session."""
    inp = state.get("input") or {}
    vin = str(inp.get("vin", ""))
    is_valid = len(vin) == 17
    return {
        "log": [f"{UNISPSC_CODE}:validate_identity(vin_valid={is_valid})"],
        "vin_verified": is_valid,
        "fleet_id": inp.get("fleet_id", "UNASSIGNED"),
    }


def assess_condition(state: State) -> dict[str, Any]:
    """Evaluate mileage and sensor health for maintenance scheduling."""
    inp = state.get("input") or {}
    mileage = inp.get("odometer", 0)
    status = "SERVICE_REQUIRED" if mileage > 50000 else "OPERATIONAL"
    return {
        "log": [f"{UNISPSC_CODE}:assess_condition(status={status})"],
        "maintenance_status": status,
        "telemetry_active": inp.get("ignition_on", False),
    }


def emit_dispatch_report(state: State) -> dict[str, Any]:
    """Finalize the vehicle state and emit the readiness result."""
    is_ready = state.get("vin_verified") and state.get("maintenance_status") == "OPERATIONAL"
    return {
        "log": [f"{UNISPSC_CODE}:emit_dispatch_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vehicle_state": {
                "fleet": state.get("fleet_id"),
                "condition": state.get("maintenance_status"),
                "telemetry": "online" if state.get("telemetry_active") else "offline",
            },
            "dispatch_ready": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_identity)
_g.add_node("assess", assess_condition)
_g.add_node("emit", emit_dispatch_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
