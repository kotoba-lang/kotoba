# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25110000"
UNISPSC_TITLE = "Logistics"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25110000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Logistics domain state
    load_status: str
    carrier_assigned: bool
    tracking_id: str
    delivery_priority: str


def ingest_shipment(state: State) -> dict[str, Any]:
    """Ingests shipment data and determines delivery priority."""
    inp = state.get("input") or {}
    weight = inp.get("weight_kg", 0)
    priority = "EXPRESS" if weight > 0 and weight < 100 else "STANDARD"
    return {
        "log": [f"{UNISPSC_CODE}:ingest_shipment"],
        "load_status": "INGESTED",
        "delivery_priority": priority,
    }


def assign_logistics_carrier(state: State) -> dict[str, Any]:
    """Simulates carrier assignment based on priority and load."""
    priority = state.get("delivery_priority", "STANDARD")
    carrier_status = priority in ["EXPRESS", "STANDARD"]
    return {
        "log": [f"{UNISPSC_CODE}:assign_logistics_carrier"],
        "carrier_assigned": carrier_status,
        "load_status": "CARRIER_PENDING" if carrier_status else "ERROR",
    }


def generate_waybill(state: State) -> dict[str, Any]:
    """Generates a tracking ID and prepares the final result."""
    assigned = state.get("carrier_assigned", False)
    t_id = f"WAY-{UNISPSC_CODE}-001" if assigned else "UNASSIGNED"
    return {
        "log": [f"{UNISPSC_CODE}:generate_waybill"],
        "tracking_id": t_id,
        "load_status": "READY_FOR_PICKUP" if assigned else "FAILED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "logistics_summary": {
                "tracking_id": t_id,
                "priority": state.get("delivery_priority"),
                "status": "COMPLETED" if assigned else "INCOMPLETE",
            },
            "ok": assigned,
        },
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_shipment)
_g.add_node("assign", assign_logistics_carrier)
_g.add_node("waybill", generate_waybill)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "assign")
_g.add_edge("assign", "waybill")
_g.add_edge("waybill", END)

graph = _g.compile()
