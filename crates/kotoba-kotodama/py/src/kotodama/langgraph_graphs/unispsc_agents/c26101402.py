# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101402 — Motor Base (segment 26).

This bespoke LangGraph agent handles state transitions for motor base specification,
including frame size validation, mounting style configuration, and structural integrity checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101402"
UNISPSC_TITLE = "Motor Base"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101402"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    frame_size: str
    mounting_style: str
    load_rating_kn: float
    is_vibration_isolated: bool


def analyze_specifications(state: State) -> dict[str, Any]:
    """Extract and validate motor frame size and expected load requirements."""
    inp = state.get("input") or {}
    frame = str(inp.get("frame_size", "NEMA-Default"))
    load = float(inp.get("required_load_kn", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications(frame={frame})"],
        "frame_size": frame,
        "load_rating_kn": load
    }


def configure_mounting(state: State) -> dict[str, Any]:
    """Determine the optimal mounting style (sliding, adjustable, or fixed) based on input."""
    inp = state.get("input") or {}
    pref = inp.get("mounting_preference", "adjustable")

    # Motor bases often require tensioning adjustments for belt-driven systems
    mounting = "SLIDING_TENSIONER" if pref == "belt" else "FIXED_HEAVY_DUTY"

    return {
        "log": [f"{UNISPSC_CODE}:configure_mounting(style={mounting})"],
        "mounting_style": mounting,
        "is_vibration_isolated": inp.get("vibration_control", False)
    }


def verify_structural_integrity(state: State) -> dict[str, Any]:
    """Perform final safety and compliance check for the motor base configuration."""
    frame = state.get("frame_size")
    mounting = state.get("mounting_style")

    # Simulate a structural verification pass
    integrity_status = "CERTIFIED" if state.get("load_rating_kn", 0) < 50.0 else "REQUIRES_REINFORCEMENT"

    return {
        "log": [f"{UNISPSC_CODE}:verify_structural_integrity({integrity_status})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "frame_size": frame,
                "mounting_style": mounting,
                "vibration_isolated": state.get("is_vibration_isolated"),
                "integrity_status": integrity_status
            },
            "status": "active"
        }
    }


_g = StateGraph(State)

_g.add_node("analyze_specifications", analyze_specifications)
_g.add_node("configure_mounting", configure_mounting)
_g.add_node("verify_structural_integrity", verify_structural_integrity)

_g.add_edge(START, "analyze_specifications")
_g.add_edge("analyze_specifications", "configure_mounting")
_g.add_edge("configure_mounting", "verify_structural_integrity")
_g.add_edge("verify_structural_integrity", END)

graph = _g.compile()
