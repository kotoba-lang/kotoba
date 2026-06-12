# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102007"
UNISPSC_TITLE = "Storage"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102007"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    storage_unit_id: str
    available_volume: float
    hazard_clearance: bool
    shelf_stable: bool


def assess_intake(state: State) -> dict[str, Any]:
    """Assess the dimensions and safety profile of the incoming storage request."""
    inp = state.get("input") or {}
    volume = inp.get("volume_cubic_meters", 1.2)
    is_hazardous = inp.get("is_hazardous", False)

    return {
        "log": [f"{UNISPSC_CODE}:assess_intake:vol={volume}:hazard={is_hazardous}"],
        "available_volume": 1000.0 - volume,
        "hazard_clearance": not is_hazardous,
    }


def assign_location(state: State) -> dict[str, Any]:
    """Determine the specific storage bin or unit ID for the item."""
    if not state.get("hazard_clearance", False):
        return {
            "log": [f"{UNISPSC_CODE}:assign_location:denied"],
            "storage_unit_id": "QUARANTINE-01",
            "shelf_stable": False,
        }

    unit_id = f"BIN-{UNISPSC_CODE}-A4"
    return {
        "log": [f"{UNISPSC_CODE}:assign_location:assigned={unit_id}"],
        "storage_unit_id": unit_id,
        "shelf_stable": True,
    }


def record_inventory(state: State) -> dict[str, Any]:
    """Commit the storage transaction to the facility records."""
    unit_id = state.get("storage_unit_id", "NONE")
    success = unit_id.startswith("BIN")

    return {
        "log": [f"{UNISPSC_CODE}:record_inventory:success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "assigned_unit": unit_id,
            "status": "STORED" if success else "FLAGGED",
            "capacity_remaining": state.get("available_volume", 0.0),
        },
    }


_g = StateGraph(State)
_g.add_node("assess", assess_intake)
_g.add_node("assign", assign_location)
_g.add_node("record", record_inventory)

_g.add_edge(START, "assess")
_g.add_edge("assess", "assign")
_g.add_edge("assign", "record")
_g.add_edge("record", END)

graph = _g.compile()
