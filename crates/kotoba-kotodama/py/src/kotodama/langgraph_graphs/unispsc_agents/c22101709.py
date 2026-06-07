# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101709"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for "Tool"
    tool_type: str
    is_calibrated: bool
    safety_rating: float
    asset_id: str


def inspect_tool(state: State) -> dict[str, Any]:
    """Validate tool specifications and check initial safety status."""
    inp = state.get("input") or {}
    tool_type = inp.get("type", "generic")
    asset_id = inp.get("asset_id", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tool:{asset_id}"],
        "tool_type": tool_type,
        "asset_id": asset_id,
        "safety_rating": 0.95 if tool_type != "power" else 0.85,
    }


def service_tool(state: State) -> dict[str, Any]:
    """Perform virtual calibration and maintenance checks."""
    tool_type = state.get("tool_type", "generic")
    # Simulate calibration logic: power tools need more specific checks
    calibrated = tool_type in ["precision", "measuring", "generic"]

    return {
        "log": [f"{UNISPSC_CODE}:service_tool:calibrated={calibrated}"],
        "is_calibrated": calibrated,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Generate the final tool registration and compliance record."""
    asset_id = state.get("asset_id", "unknown")
    is_calibrated = state.get("is_calibrated", False)
    safety_rating = state.get("safety_rating", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset_id": asset_id,
            "operational_ready": is_calibrated and safety_rating > 0.8,
            "status": "active" if is_calibrated else "maintenance_required",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_tool)
_g.add_node("service", service_tool)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "service")
_g.add_edge("service", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
