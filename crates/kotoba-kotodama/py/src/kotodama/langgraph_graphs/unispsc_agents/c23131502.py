# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23131502 — Cutting Machine (segment 23).

Bespoke graph logic for industrial cutting operations, including material
configuration, execution simulation, and quality control verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23131502"
UNISPSC_TITLE = "Cutting Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23131502"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Cutting Machine
    material_type: str
    target_dimensions: dict[str, float]
    blade_speed_rpm: int
    cut_precision_mm: float
    safety_interlock_active: bool


def initialize_job(state: State) -> dict[str, Any]:
    """Validates input parameters and configures the machine state."""
    inp = state.get("input") or {}
    material = inp.get("material", "industrial_grade_steel")
    dims = inp.get("dimensions", {"length": 100.0, "width": 50.0})

    return {
        "log": [f"{UNISPSC_CODE}:initialize_job"],
        "material_type": material,
        "target_dimensions": dims,
        "safety_interlock_active": True,
        "blade_speed_rpm": 3000 if material == "wood" else 1500,
    }


def execute_cut(state: State) -> dict[str, Any]:
    """Simulates the physical cutting process based on configuration."""
    material = state.get("material_type", "unknown")
    speed = state.get("blade_speed_rpm", 0)

    # Simulate a successful high-precision cut
    return {
        "log": [f"{UNISPSC_CODE}:execute_cut(speed={speed}, material={material})"],
        "cut_precision_mm": 0.05,
    }


def quality_control(state: State) -> dict[str, Any]:
    """Verifies the output dimensions against target specifications."""
    precision = state.get("cut_precision_mm", 1.0)
    is_ok = precision < 0.1

    return {
        "log": [f"{UNISPSC_CODE}:quality_control(ok={is_ok})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "job_status": "completed",
            "quality_pass": is_ok,
            "precision_achieved": precision,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_job", initialize_job)
_g.add_node("execute_cut", execute_cut)
_g.add_node("quality_control", quality_control)

_g.add_edge(START, "initialize_job")
_g.add_edge("initialize_job", "execute_cut")
_g.add_edge("execute_cut", "quality_control")
_g.add_edge("quality_control", END)

graph = _g.compile()
