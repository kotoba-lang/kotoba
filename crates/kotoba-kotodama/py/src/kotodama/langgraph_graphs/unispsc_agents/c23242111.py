# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242111 — Lathe (segment 23).
Bespoke logic for precision machining and industrial turning operations.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242111"
UNISPSC_TITLE = "Lathe"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242111"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific state for industrial lathe operations
    spindle_speed_rpm: int
    tool_geometry: str
    material_hardness: float
    safety_protocol_active: bool


def setup_workpiece(state: State) -> dict[str, Any]:
    """Initializes the lathe with workpiece specifications and safety parameters."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    speed = inp.get("target_rpm", 1500)

    # Calculate safety protocol activation based on RPM limits
    safety = 0 < speed < 4500

    return {
        "log": [f"{UNISPSC_CODE}:setup_workpiece - Material: {material}, RPM: {speed}"],
        "spindle_speed_rpm": speed,
        "material_hardness": 0.85 if material == "carbon_steel" else 0.5,
        "safety_protocol_active": safety,
    }


def perform_turning(state: State) -> dict[str, Any]:
    """Executes the turning process if safety protocols are met."""
    if not state.get("safety_protocol_active"):
        return {
            "log": [f"{UNISPSC_CODE}:perform_turning - SAFETY INTERLOCK TRIPPED"],
            "tool_geometry": "NOT_ENGAGED",
        }

    # Logic for selecting tool geometry based on material hardness
    hardness = state.get("material_hardness", 0.0)
    geometry = "carbide_tip" if hardness > 0.7 else "high_speed_steel"

    return {
        "log": [f"{UNISPSC_CODE}:perform_turning - Engaged tool: {geometry}"],
        "tool_geometry": geometry,
    }


def verify_precision(state: State) -> dict[str, Any]:
    """Performs final inspection of the machined part and emits results."""
    geometry = state.get("tool_geometry", "")
    ok = geometry != "NOT_ENGAGED" and geometry != ""

    return {
        "log": [f"{UNISPSC_CODE}:verify_precision - Integrity check: {ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "machining_completed": ok,
            "final_tooling": geometry,
            "status": "OPERATIONAL_SUCCESS" if ok else "ERROR_SAFETY_HALT",
        },
    }


_g = StateGraph(State)
_g.add_node("setup", setup_workpiece)
_g.add_node("turn", perform_turning)
_g.add_node("verify", verify_precision)

_g.add_edge(START, "setup")
_g.add_edge("setup", "turn")
_g.add_edge("turn", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
