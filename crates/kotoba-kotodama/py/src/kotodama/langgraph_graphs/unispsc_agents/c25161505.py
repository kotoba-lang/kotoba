# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25161505 — Bike (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161505"
UNISPSC_TITLE = "Bike"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    frame_material: str
    gearing_verified: bool
    safety_check_status: str
    tire_pressure_verified: bool


def inspect_build(state: State) -> dict[str, Any]:
    """Inspects the physical properties of the bicycle build."""
    inp = state.get("input") or {}
    frame = inp.get("frame", "Carbon Fiber")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_build"],
        "frame_material": frame,
        "gearing_verified": True,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Verifies safety standards for the bike's operation."""
    # Simulation of safety verification logic
    frame_ok = state.get("frame_material") != "Unknown"
    status = "Certified" if frame_ok else "Rejected"
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_check_status": status,
        "tire_pressure_verified": True,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the actor state and prepares the output result."""
    passed = state.get("safety_check_status") == "Certified"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verified": passed,
            "specifications": {
                "material": state.get("frame_material"),
                "safety": state.get("safety_check_status"),
                "tires": "Checked" if state.get("tire_pressure_verified") else "Pending"
            }
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_build", inspect_build)
_g.add_node("verify_safety", verify_safety)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "inspect_build")
_g.add_edge("inspect_build", "verify_safety")
_g.add_edge("verify_safety", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
