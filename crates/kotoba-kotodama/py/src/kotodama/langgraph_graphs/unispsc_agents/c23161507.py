# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161507 — Lathe Spec.

Bespoke graph logic for defining and validating industrial lathe specifications.
Handles geometric constraints, spindle capacity, and control system classification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161507"
UNISPSC_TITLE = "Lathe Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Lathe Spec
    swing_diameter: float
    center_distance: float
    spindle_bore: float
    max_rpm: int
    is_cnc: bool


def parse_geometry(state: State) -> dict[str, Any]:
    """Extracts and validates physical dimensions of the lathe machine."""
    inp = state.get("input") or {}
    swing = float(inp.get("swing_diameter", 0.0))
    dist = float(inp.get("center_distance", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:parse_geometry"],
        "swing_diameter": swing,
        "center_distance": dist,
    }


def evaluate_capacity(state: State) -> dict[str, Any]:
    """Analyzes spindle and control capabilities."""
    inp = state.get("input") or {}
    bore = float(inp.get("spindle_bore", 0.0))
    rpm = int(inp.get("max_rpm", 0))
    cnc = bool(inp.get("is_cnc", False))

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_capacity"],
        "spindle_bore": bore,
        "max_rpm": rpm,
        "is_cnc": cnc,
    }


def generate_spec_sheet(state: State) -> dict[str, Any]:
    """Compiles the final technical specification object."""
    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "technical_data": {
            "swing_mm": state.get("swing_diameter"),
            "distance_mm": state.get("center_distance"),
            "bore_mm": state.get("spindle_bore"),
            "rpm_limit": state.get("max_rpm"),
            "control_type": "CNC" if state.get("is_cnc") else "Manual",
        },
        "status": "validated" if state.get("swing_diameter", 0) > 0 else "incomplete",
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_spec_sheet"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("parse_geometry", parse_geometry)
_g.add_node("evaluate_capacity", evaluate_capacity)
_g.add_node("generate_spec_sheet", generate_spec_sheet)

_g.add_edge(START, "parse_geometry")
_g.add_edge("parse_geometry", "evaluate_capacity")
_g.add_edge("evaluate_capacity", "generate_spec_sheet")
_g.add_edge("generate_spec_sheet", END)

graph = _g.compile()
