# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352400 — Silicon (segment 12).

Bespoke graph for Silicon (12352400) handling material purity, form factor,
and grade classification for semiconductor and industrial applications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352400"
UNISPSC_TITLE = "Silicon"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_percentage: float
    form_factor: str  # e.g., "wafer", "ingot", "polysilicon"
    grade_category: str  # e.g., "Electronic", "Solar", "Metallurgical"
    is_semiconductor_grade: bool


def validate_material(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    form = str(inp.get("form", "raw")).lower()

    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "purity_percentage": purity,
        "form_factor": form,
    }


def assess_grade(state: State) -> dict[str, Any]:
    purity = state.get("purity_percentage", 0.0)

    # 9N purity (99.9999999%) is typical for electronic grade
    if purity >= 99.9999999:
        grade = "Electronic"
        is_semi = True
    elif purity >= 99.9999:
        grade = "Solar"
        is_semi = False
    elif purity >= 98.0:
        grade = "Metallurgical"
        is_semi = False
    else:
        grade = "Sub-standard"
        is_semi = False

    return {
        "log": [f"{UNISPSC_CODE}:assess_grade"],
        "grade_category": grade,
        "is_semiconductor_grade": is_semi
    }


def finalize_spec(state: State) -> dict[str, Any]:
    purity = state.get("purity_percentage", 0.0)
    grade = state.get("grade_category", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "purity": purity,
                "grade": grade,
                "form": state.get("form_factor"),
                "semiconductor_ready": state.get("is_semiconductor_grade"),
            },
            "ok": purity >= 98.0,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("assess_grade", assess_grade)
_g.add_node("finalize_spec", finalize_spec)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "assess_grade")
_g.add_edge("assess_grade", "finalize_spec")
_g.add_edge("finalize_spec", END)

graph = _g.compile()
