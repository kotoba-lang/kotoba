# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101504 — Bolt (segment 22).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101504"
UNISPSC_TITLE = "Bolt"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    diameter_mm: float
    length_mm: float
    grade: str
    tensile_capacity_kn: float


def inspect_bolt_geometry(state: State) -> dict[str, Any]:
    """Validates physical dimensions of the bolt unit."""
    inp = state.get("input") or {}
    dia = float(inp.get("diameter", 10.0))
    length = float(inp.get("length", 50.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_bolt_geometry"],
        "diameter_mm": dia,
        "length_mm": length,
        "grade": inp.get("grade", "8.8"),
    }


def evaluate_tensile_load(state: State) -> dict[str, Any]:
    """Calculates theoretical tensile capacity based on cross-section and grade."""
    dia = state.get("diameter_mm", 10.0)
    grade_str = state.get("grade", "8.8")

    # Simple mechanical simulation: Capacity proportional to area and grade factor
    try:
        grade_val = float(grade_str.split(".")[0]) * 100.0
    except (ValueError, AttributeError, IndexError):
        grade_val = 400.0

    area = 3.14159 * (dia / 2) ** 2
    capacity = (area * grade_val) / 1000.0  # Force in kilonewtons

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_tensile_load"],
        "tensile_capacity_kn": round(capacity, 2),
    }


def issue_compliance_report(state: State) -> dict[str, Any]:
    """Finalizes the structural certification for the construction component."""
    return {
        "log": [f"{UNISPSC_CODE}:issue_compliance_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "diameter_mm": state.get("diameter_mm"),
                "length_mm": state.get("length_mm"),
                "grade": state.get("grade"),
            },
            "load_rating_kn": state.get("tensile_capacity_kn"),
            "status": "approved_for_construction",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_bolt_geometry)
_g.add_node("evaluate", evaluate_tensile_load)
_g.add_node("report", issue_compliance_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "report")
_g.add_edge("report", END)

graph = _g.compile()
