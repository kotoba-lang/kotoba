# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111704 — Ship (segment 25).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111704"
UNISPSC_TITLE = "Ship"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    vessel_name: str
    imo_number: str
    deadweight_tonnage: int
    hull_type: str
    navigation_status: str


def register_vessel(state: State) -> dict[str, Any]:
    """Registers the ship and its IMO identifier."""
    inp = state.get("input") or {}
    vessel_name = inp.get("vessel_name", "Spirit of the Sea")
    imo = inp.get("imo_number", "IMO9876543")
    return {
        "log": [f"{UNISPSC_CODE}:register_vessel:{vessel_name}:{imo}"],
        "vessel_name": vessel_name,
        "imo_number": imo,
    }


def inspect_hull(state: State) -> dict[str, Any]:
    """Performs hull type and tonnage verification."""
    inp = state.get("input") or {}
    hull = inp.get("hull_type", "Double Hull")
    dwt = inp.get("deadweight_tonnage", 85000)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_hull:{hull}:{dwt} DWT"],
        "hull_type": hull,
        "deadweight_tonnage": dwt,
    }


def deploy_voyage(state: State) -> dict[str, Any]:
    """Finalizes the ship status for deployment."""
    vessel = state.get("vessel_name", "Unknown")
    status = "Active/Seaworthy" if state.get("imo_number") else "Pending Registry"
    return {
        "log": [f"{UNISPSC_CODE}:deploy_voyage:Status set to {status}"],
        "navigation_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vessel": vessel,
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("register_vessel", register_vessel)
_g.add_node("inspect_hull", inspect_hull)
_g.add_node("deploy_voyage", deploy_voyage)

_g.add_edge(START, "register_vessel")
_g.add_edge("register_vessel", "inspect_hull")
_g.add_edge("inspect_hull", "deploy_voyage")
_g.add_edge("deploy_voyage", END)

graph = _g.compile()
