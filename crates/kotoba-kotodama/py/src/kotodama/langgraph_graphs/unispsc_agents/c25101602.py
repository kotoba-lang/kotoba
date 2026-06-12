# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101602"
UNISPSC_TITLE = "Tow Truck"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Tow Truck operations
    tow_truck_id: str
    target_vehicle_vin: str
    tow_status: str
    safety_inspection_verified: bool
    destination_depot: str


def dispatch_tow_truck(state: State) -> dict[str, Any]:
    """Validates dispatch request and assigns a specific tow truck unit."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_tow_truck"],
        "tow_truck_id": "UNIT-704-HEAVY",
        "target_vehicle_vin": inp.get("vin", "VIN_UNKNOWN"),
        "tow_status": "dispatched",
        "destination_depot": inp.get("depot", "DEPOT_MAIN"),
    }


def execute_towing_operation(state: State) -> dict[str, Any]:
    """Simulates the physical recovery and transit of the target vehicle."""
    return {
        "log": [f"{UNISPSC_CODE}:execute_towing_operation"],
        "safety_inspection_verified": True,
        "tow_status": "in_transit",
    }


def complete_service_cycle(state: State) -> dict[str, Any]:
    """Finalizes the towing record and confirms delivery to the depot."""
    return {
        "log": [f"{UNISPSC_CODE}:complete_service_cycle"],
        "tow_status": "completed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "truck_unit": state.get("tow_truck_id"),
            "target_vin": state.get("target_vehicle_vin"),
            "destination": state.get("destination_depot"),
            "operation_status": "SUCCESSFUL_RECOVERY",
        },
    }


_g = StateGraph(State)

_g.add_node("dispatch", dispatch_tow_truck)
_g.add_node("tow", execute_towing_operation)
_g.add_node("complete", complete_service_cycle)

_g.add_edge(START, "dispatch")
_g.add_edge("dispatch", "tow")
_g.add_edge("tow", "complete")
_g.add_edge("complete", END)

graph = _g.compile()
