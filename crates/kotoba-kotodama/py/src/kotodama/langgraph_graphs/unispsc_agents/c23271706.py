# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271706"
UNISPSC_TITLE = "Desoldering"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    temperature_celsius: int
    tool_type: str
    joint_integrity: str
    residue_cleared: bool
    is_success: bool


def analyze_joint(state: State) -> dict[str, Any]:
    """Determines the required thermal profile and tool selection based on alloy type."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "lead-free")

    # Lead-free solder typically requires higher temperatures than leaded solder.
    temp = 360 if alloy == "lead-free" else 310
    tool = inp.get("tool", "vacuum_desoldering_station")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_joint - alloy: {alloy}, target: {temp}C"],
        "temperature_celsius": temp,
        "tool_type": tool,
        "joint_integrity": "intact",
    }


def execute_desoldering(state: State) -> dict[str, Any]:
    """Simulates the thermal application and solder extraction process."""
    temp = state.get("temperature_celsius", 0)
    tool = state.get("tool_type", "manual_wick")

    # Simulate extraction success: requires sufficient heat.
    extraction_ok = temp >= 300
    status = "released" if extraction_ok else "thermal_insufficiency"

    return {
        "log": [f"{UNISPSC_CODE}:execute_desoldering - using {tool} at {temp}C"],
        "joint_integrity": status,
        "residue_cleared": extraction_ok,
    }


def final_inspection(state: State) -> dict[str, Any]:
    """Verifies that the PCB pads are clean and component leads are free of solder."""
    integrity = state.get("joint_integrity")
    cleared = state.get("residue_cleared", False)
    success = (integrity == "released") and cleared

    return {
        "log": [f"{UNISPSC_CODE}:final_inspection - verified: {success}"],
        "is_success": success,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "COMPLETED" if success else "FAILED",
            "telemetry": {
                "final_temp": state.get("temperature_celsius"),
                "tool_used": state.get("tool_type"),
                "integrity": integrity
            }
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_joint)
_g.add_node("desolder", execute_desoldering)
_g.add_node("inspect", final_inspection)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "desolder")
_g.add_edge("desolder", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
