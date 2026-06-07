# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111801 — Reservoir (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111801"
UNISPSC_TITLE = "Reservoir"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Reservoir storage and hydraulic control
    capacity_m3: float
    current_level_m: float
    discharge_rate_m3s: float
    spillway_active: bool


def assess_storage(state: State) -> dict[str, Any]:
    """Inspects the current storage levels and physical capacity of the reservoir."""
    inp = state.get("input") or {}
    # Default to nominal values if not provided in input
    capacity = float(inp.get("capacity_m3", 1000000.0))
    current_level = float(inp.get("current_level_m", 500000.0))

    return {
        "log": [f"{UNISPSC_CODE}:assess_storage: level={current_level}m3, capacity={capacity}m3"],
        "capacity_m3": capacity,
        "current_level_m": current_level,
    }


def regulate_outflow(state: State) -> dict[str, Any]:
    """Calculates discharge rate and spillway status based on hydrological state."""
    level = state.get("current_level_m", 0.0)
    capacity = state.get("capacity_m3", 1.0)

    fill_ratio = level / capacity
    # Activate spillway if above 95% capacity
    spillway = fill_ratio > 0.95
    # Base discharge depends on reservoir head/fill
    discharge = 50.0 if fill_ratio > 0.5 else 10.0

    if spillway:
        discharge += 250.0  # Significant increase in discharge through spillway

    return {
        "log": [f"{UNISPSC_CODE}:regulate_outflow: ratio={fill_ratio:.2%}, spillway={spillway}"],
        "discharge_rate_m3s": discharge,
        "spillway_active": spillway,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final operational report for the Reservoir system."""
    spillway = state.get("spillway_active", False)
    status_msg = "Critical Overflow" if spillway else "Nominal Operations"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report: status={status_msg}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "capacity": state.get("capacity_m3"),
                "level": state.get("current_level_m"),
                "discharge": state.get("discharge_rate_m3s"),
                "spillway_active": spillway,
            },
            "status": status_msg,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_storage", assess_storage)
_g.add_node("regulate_outflow", regulate_outflow)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "assess_storage")
_g.add_edge("assess_storage", "regulate_outflow")
_g.add_edge("regulate_outflow", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
