# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111601"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for maritime tanker operations (UNISPSC 25111601)
    vessel_id: str
    cargo_type: str
    deadweight_tonnage: float
    is_safety_verified: bool
    port_clearance_code: str


def register_vessel(state: State) -> dict[str, Any]:
    """Registers the tanker vessel and its cargo manifest."""
    inp = state.get("input") or {}
    v_id = inp.get("vessel_id", "TANKER-ALPHA-01")
    cargo = inp.get("cargo", "Refined Petroleum")
    tonnage = float(inp.get("tonnage", 150000.0))

    return {
        "log": [f"{UNISPSC_CODE}:register_vessel -> {v_id}"],
        "vessel_id": v_id,
        "cargo_type": cargo,
        "deadweight_tonnage": tonnage,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies maritime safety and environmental compliance for the tanker."""
    # Logic: Assume compliance if tonnage is within standard limits for the vessel class
    is_safe = state.get("deadweight_tonnage", 0.0) < 500000.0
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance -> {is_safe}"],
        "is_safety_verified": is_safe,
        "port_clearance_code": "CLS-VER-001" if is_safe else "REJECTED",
    }


def authorize_docking(state: State) -> dict[str, Any]:
    """Finalizes authorization for the tanker to proceed with docking operations."""
    authorized = state.get("is_safety_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:authorize_docking -> {authorized}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel_id": state.get("vessel_id"),
            "authorized": authorized,
            "clearance": state.get("port_clearance_code"),
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
        },
    }


_g = StateGraph(State)
_g.add_node("register", register_vessel)
_g.add_node("verify", verify_compliance)
_g.add_node("authorize", authorize_docking)

_g.add_edge(START, "register")
_g.add_edge("register", "verify")
_g.add_edge("verify", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
