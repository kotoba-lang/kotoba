# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172506"
UNISPSC_TITLE = "Tire"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_psi: float
    tread_depth_mm: float
    rim_diameter_in: int
    is_safe: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Node to inspect the physical specifications of the tire."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure_psi", 32.0))
    rim = int(inp.get("rim_diameter_in", 17))
    tread = float(inp.get("tread_depth_mm", 8.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "pressure_psi": pressure,
        "rim_diameter_in": rim,
        "tread_depth_mm": tread,
    }


def evaluate_safety_standards(state: State) -> dict[str, Any]:
    """Node to evaluate safety standards based on tread depth and pressure."""
    tread = state.get("tread_depth_mm", 0.0)
    pressure = state.get("pressure_psi", 0.0)

    # Minimum legal tread depth in many jurisdictions is 1.6mm.
    # Standard passenger vehicle tire pressure is typically 30-35 psi.
    is_safe = (tread >= 1.6) and (28.0 <= pressure <= 42.0)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_safety_standards"],
        "is_safe": is_safe,
    }


def certify_compliance(state: State) -> dict[str, Any]:
    """Node to emit the final certification result for the Tire actor."""
    is_safe = state.get("is_safe", False)
    rim = state.get("rim_diameter_in", 0)
    tread = state.get("tread_depth_mm", 0.0)

    status = "CERTIFIED" if is_safe else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_compliance"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "rim_diameter": rim,
            "tread_depth": tread,
            "compliance_status": status,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("evaluate", evaluate_safety_standards)
_g.add_node("certify", certify_compliance)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
