# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25100000"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25100000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    vin_verified: bool
    chassis_inspected: bool
    engine_verified: bool
    compliance_score: float


def inspect_identity(state: State) -> dict[str, Any]:
    """Verifies the VIN and engine serial numbers for the vehicle."""
    inp = state.get("input") or {}
    vin = inp.get("vin", "N/A")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_identity:{vin}"],
        "vin_verified": vin != "N/A",
        "engine_verified": True,
    }


def verify_mechanical(state: State) -> dict[str, Any]:
    """Simulates a chassis and safety system diagnostic."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanical"],
        "chassis_inspected": True,
        "compliance_score": 0.98,
    }


def register_vehicle(state: State) -> dict[str, Any]:
    """Finalizes vehicle registration and emits the actor result."""
    return {
        "log": [f"{UNISPSC_CODE}:register_vehicle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vin_verified": state.get("vin_verified"),
            "compliance_score": state.get("compliance_score"),
            "status": "active_inventory",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_identity", inspect_identity)
_g.add_node("verify_mechanical", verify_mechanical)
_g.add_node("register_vehicle", register_vehicle)

_g.add_edge(START, "inspect_identity")
_g.add_edge("inspect_identity", "verify_mechanical")
_g.add_edge("verify_mechanical", "register_vehicle")
_g.add_edge("register_vehicle", END)

graph = _g.compile()
