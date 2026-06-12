# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151513 — Weld (segment 23).

Bespoke LangGraph logic for industrial welding processes. This agent
manages welding specification validation, process simulation, and quality
verification for the UNISPSC 23151513 commodity code.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151513"
UNISPSC_TITLE = "Weld"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151513"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_type: str
    weld_method: str
    thickness_mm: float
    inspection_passed: bool


def configure_weld(state: State) -> dict[str, Any]:
    """Validates and extracts welding parameters from input."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    method = inp.get("method", "SMAW")
    thickness = float(inp.get("thickness", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:configure_weld({material}, {method})"],
        "material_type": material,
        "weld_method": method,
        "thickness_mm": thickness,
    }


def execute_weld(state: State) -> dict[str, Any]:
    """Simulates the physical welding process and sets inspection flag."""
    material = state.get("material_type")
    thickness = state.get("thickness_mm", 0.0)

    # Industrial logic: welds over 50mm thickness require specialized testing
    passed = thickness < 50.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_weld_on_{material}"],
        "inspection_passed": passed,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final actor response based on process outcomes."""
    passed = state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material": state.get("material_type"),
            "status": "COMPLETED" if passed else "REJECTED_BY_INSPECTION",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_weld)
_g.add_node("execute", execute_weld)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "configure")
_g.add_edge("configure", "execute")
_g.add_edge("execute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
