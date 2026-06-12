# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241507"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Drilling/Milling Processing Centers
    machining_mode: str
    tool_sequence: list[str]
    spindle_calibration_offset: float
    safety_interlock_active: bool


def analyze_machining_requirements(state: State) -> dict[str, Any]:
    """Analyzes the input specifications for the processing center workflow."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "milling")
    precision_req = inp.get("precision", "standard")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_machining_requirements"],
        "machining_mode": mode,
        "safety_interlock_active": bool(inp),
    }


def configure_tooling_path(state: State) -> dict[str, Any]:
    """Determines the appropriate tool sequence and calibration offsets."""
    mode = state.get("machining_mode", "milling")

    if mode == "drilling":
        tools = ["center_drill", "twist_drill_8mm", "reamer_8h7"]
        offset = 0.015
    elif mode == "milling":
        tools = ["face_mill_50mm", "end_mill_12mm", "ball_nose_6mm"]
        offset = 0.005
    else:
        tools = ["generic_processing_tool"]
        offset = 0.1

    return {
        "log": [f"{UNISPSC_CODE}:configure_tooling_path"],
        "tool_sequence": tools,
        "spindle_calibration_offset": offset,
    }


def emit_processing_status(state: State) -> dict[str, Any]:
    """Finalizes the processing center state and emits the manifest."""
    is_safe = state.get("safety_interlock_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_processing_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_safe,
            "machining_data": {
                "mode": state.get("machining_mode"),
                "tools": state.get("tool_sequence", []),
                "offset_mm": state.get("spindle_calibration_offset"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_machining_requirements)
_g.add_node("configure", configure_tooling_path)
_g.add_node("emit", emit_processing_status)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "configure")
_g.add_edge("configure", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
