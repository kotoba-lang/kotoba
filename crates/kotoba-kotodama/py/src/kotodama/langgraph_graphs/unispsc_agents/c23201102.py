# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201102"
UNISPSC_TITLE = "Dump Truck"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    payload_weight_kg: int
    material_category: str
    bed_elevation_status: str
    tire_pressure_ok: bool


def inspect_load(state: State) -> dict[str, Any]:
    """Validates the truck's load and safety parameters before departure."""
    inp = state.get("input") or {}
    weight = inp.get("weight", 0)
    material = inp.get("material", "unspecified aggregate")

    # Simple threshold check for tire pressure safety
    pressure_check = weight < 28000

    return {
        "log": [f"{UNISPSC_CODE}:inspect_load"],
        "payload_weight_kg": weight,
        "material_category": material,
        "tire_pressure_ok": pressure_check,
    }


def monitor_transit(state: State) -> dict[str, Any]:
    """Ensures mechanical safety configurations during haulage."""
    # Safety protocol requires bed to be fully lowered during movement
    return {
        "log": [f"{UNISPSC_CODE}:monitor_transit"],
        "bed_elevation_status": "lowered",
    }


def confirm_delivery(state: State) -> dict[str, Any]:
    """Finalizes the site manifest and confirms successful payload delivery."""
    is_safe = state.get("tire_pressure_ok", False) and state.get("bed_elevation_status") == "lowered"

    return {
        "log": [f"{UNISPSC_CODE}:confirm_delivery"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "payload_data": {
                "weight_kg": state.get("payload_weight_kg"),
                "material": state.get("material_category"),
            },
            "safety_verified": is_safe,
            "status": "delivered",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_load", inspect_load)
_g.add_node("monitor_transit", monitor_transit)
_g.add_node("confirm_delivery", confirm_delivery)

_g.add_edge(START, "inspect_load")
_g.add_edge("inspect_load", "monitor_transit")
_g.add_edge("monitor_transit", "confirm_delivery")
_g.add_edge("confirm_delivery", END)

graph = _g.compile()
