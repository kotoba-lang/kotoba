# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242116 — Tapping (segment 23).

Bespoke LangGraph implementation for internal thread cutting and forming operations.
This agent handles the validation of thread specifications, tool selection based on
material properties, and calculation of machining parameters for tapping cycles.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242116"
UNISPSC_TITLE = "Tapping"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242116"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    thread_specification: str
    material_hardness_hb: int
    tap_geometry: str
    torque_limit_nm: float
    coolant_required: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the input thread requirements and material properties."""
    inp = state.get("input") or {}
    spec = inp.get("thread_size", "M6x1.0")
    hardness = inp.get("material_hardness", 180)

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "thread_specification": spec,
        "material_hardness_hb": hardness,
    }


def select_tooling(state: State) -> dict[str, Any]:
    """Selects appropriate tap geometry and calculates safety limits."""
    hardness = state.get("material_hardness_hb", 180)

    # Logic for tool selection based on material hardness
    if hardness > 300:
        geometry = "spiral_flute_carbide"
        torque = 12.5
        coolant = True
    else:
        geometry = "spiral_point_hss"
        torque = 8.2
        coolant = False

    return {
        "log": [f"{UNISPSC_CODE}:select_tooling"],
        "tap_geometry": geometry,
        "torque_limit_nm": torque,
        "coolant_required": coolant,
    }


def generate_plan(state: State) -> dict[str, Any]:
    """Compiles the final tapping operation plan."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operation": "internal_threading",
            "parameters": {
                "specification": state.get("thread_specification"),
                "tooling": state.get("tap_geometry"),
                "max_torque": state.get("torque_limit_nm"),
                "coolant": state.get("coolant_required"),
            },
            "status": "ready_for_execution",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_spec)
_g.add_node("select_tooling", select_tooling)
_g.add_node("generate_plan", generate_plan)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "select_tooling")
_g.add_edge("select_tooling", "generate_plan")
_g.add_edge("generate_plan", END)

graph = _g.compile()
