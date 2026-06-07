# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111701 — Submarine (segment 25).

Bespoke graph for managing submarine mission lifecycle, including hull integrity
validation, depth adjustment, and telemetry emission.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111701"
UNISPSC_TITLE = "Submarine"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    hull_integrity: float
    depth_meters: int
    ballast_tank_level: float
    stealth_active: bool


def inspect_hull(state: State) -> dict[str, Any]:
    """Validate the submarine's structural integrity before diving."""
    inp = state.get("input") or {}
    initial_integrity = inp.get("initial_integrity", 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hull"],
        "hull_integrity": initial_integrity,
        "stealth_active": initial_integrity > 0.9,
    }


def adjust_depth(state: State) -> dict[str, Any]:
    """Calculate and set the dive depth based on safety constraints."""
    inp = state.get("input") or {}
    requested_depth = inp.get("target_depth", 100)
    current_integrity = state.get("hull_integrity", 1.0)

    # Depth limit based on hull integrity: 1.0 integrity = 1000m max depth
    max_safe_depth = int(current_integrity * 1000)
    actual_depth = min(requested_depth, max_safe_depth)

    return {
        "log": [f"{UNISPSC_CODE}:adjust_depth"],
        "depth_meters": actual_depth,
        "ballast_tank_level": actual_depth / 1000.0 if max_safe_depth > 0 else 1.0,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Generate the final mission status and submarine telemetry."""
    integrity = state.get("hull_integrity", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "depth_m": state.get("depth_meters"),
                "integrity_pct": integrity * 100,
                "stealth": state.get("stealth_active"),
                "ballast": state.get("ballast_tank_level"),
            },
            "status": "operational" if integrity > 0.7 else "maintenance_required",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_hull", inspect_hull)
_g.add_node("adjust_depth", adjust_depth)
_g.add_node("emit_telemetry", emit_telemetry)

_g.add_edge(START, "inspect_hull")
_g.add_edge("inspect_hull", "adjust_depth")
_g.add_edge("adjust_depth", "emit_telemetry")
_g.add_edge("emit_telemetry", END)

graph = _g.compile()
