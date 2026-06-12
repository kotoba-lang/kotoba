# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102200 — Mining Part (segment 20).

Bespoke graph logic for mining parts metallurgy inspection and tolerance calculation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102200"
UNISPSC_TITLE = "Mining Part"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Mining Part
    metallurgy_grade: str
    stress_tolerance_mpa: int
    wear_factor: float
    inspection_passed: bool


def inspect_metallurgy(state: State) -> dict[str, Any]:
    """Analyzes the material composition of the mining part component."""
    inp = state.get("input") or {}
    composition = inp.get("composition", "Standard Steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_metallurgy"],
        "metallurgy_grade": composition,
        "inspection_passed": "Hazardous" not in composition
    }


def calculate_tolerance(state: State) -> dict[str, Any]:
    """Calculates mechanical stress tolerance and expected wear coefficient."""
    grade = state.get("metallurgy_grade", "Standard Steel")

    # Basic lookup for mining environment stress factors
    tolerances = {"Tungsten Carbide": 1500, "High Carbon Steel": 800}
    tolerance = tolerances.get(grade, 400)

    # Calculate wear factor based on tolerance levels
    wear = round(1.0 / (tolerance / 100.0), 3) if tolerance > 0 else 1.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_tolerance"],
        "stress_tolerance_mpa": tolerance,
        "wear_factor": wear
    }


def generate_report(state: State) -> dict[str, Any]:
    """Generates the final certification report for the mining component."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "metallurgy": state.get("metallurgy_grade"),
            "max_stress_mpa": state.get("stress_tolerance_mpa"),
            "wear_coefficient": state.get("wear_factor"),
            "certified": state.get("inspection_passed")
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_metallurgy)
_g.add_node("calculate", calculate_tolerance)
_g.add_node("generate", generate_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
