# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102101 — Tillage (segment 21).

Bespoke logic for tillage operations, including soil assessment,
equipment selection, and depth monitoring.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102101"
UNISPSC_TITLE = "Tillage"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Tillage
    soil_type: str
    target_depth_cm: float
    equipment_type: str
    moisture_index: float
    area_hectares: float


def assess_soil(state: State) -> dict[str, Any]:
    """Node: Evaluate soil conditions to determine tillage feasibility."""
    inp = state.get("input") or {}
    s_type = inp.get("soil_type", "loam")
    moisture = inp.get("moisture", 0.15)

    return {
        "log": [f"{UNISPSC_CODE}:assess_soil(type={s_type}, moisture={moisture})"],
        "soil_type": s_type,
        "moisture_index": moisture,
        "area_hectares": float(inp.get("area", 1.0))
    }


def plan_tillage(state: State) -> dict[str, Any]:
    """Node: Select equipment and depth based on soil assessment."""
    s_type = state.get("soil_type", "unknown")

    # Simple logic to determine equipment and depth requirements
    if s_type == "clay":
        eq = "subsoiler"
        depth = 30.0
    elif s_type == "sandy":
        eq = "disk_harrow"
        depth = 15.0
    else:
        eq = "chisel_plow"
        depth = 20.0

    return {
        "log": [f"{UNISPSC_CODE}:plan_tillage(eq={eq}, depth={depth})"],
        "equipment_type": eq,
        "target_depth_cm": depth
    }


def execute_tillage(state: State) -> dict[str, Any]:
    """Node: Finalize tillage operation and prepare result."""
    return {
        "log": [f"{UNISPSC_CODE}:execute_tillage"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operations": {
                "equipment": state.get("equipment_type"),
                "depth_cm": state.get("target_depth_cm"),
                "area": state.get("area_hectares")
            },
            "status": "completed",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_soil", assess_soil)
_g.add_node("plan_tillage", plan_tillage)
_g.add_node("execute_tillage", execute_tillage)

_g.add_edge(START, "assess_soil")
_g.add_edge("assess_soil", "plan_tillage")
_g.add_edge("plan_tillage", "execute_tillage")
_g.add_edge("execute_tillage", END)

graph = _g.compile()
