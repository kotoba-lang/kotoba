# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111505 — Fastener (segment 20).
Bespoke implementation for fastener engineering analysis and specification.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111505"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Fastener domain fields
    material_alloy: str
    tensile_strength_mpa: int
    thread_pitch_mm: float
    coating_type: str
    compliance_standard: str


def evaluate_material(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "Steel Grade 8.8")
    # Base strength for common fastener grades
    strength = 800 if "8.8" in alloy else 1040 if "10.9" in alloy else 640
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_material"],
        "material_alloy": alloy,
        "tensile_strength_mpa": strength,
        "compliance_standard": "ISO 898-1"
    }


def analyze_threading(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    nominal_dia = inp.get("diameter_mm", 10.0)
    # Heuristic for coarse pitch
    pitch = 1.5 if nominal_dia >= 10 else 1.25 if nominal_dia >= 8 else 1.0
    return {
        "log": [f"{UNISPSC_CODE}:analyze_threading"],
        "thread_pitch_mm": pitch,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    alloy = state.get("material_alloy", "Unknown")
    coating = "Zinc Flake" if "8.8" in alloy else "Phosphate"

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "technical_data": {
            "alloy": alloy,
            "tensile_strength": f"{state.get('tensile_strength_mpa')} MPa",
            "pitch": f"{state.get('thread_pitch_mm')} mm",
            "standard": state.get("compliance_standard"),
            "coating": coating
        },
        "verification": "COMPLETE"
    }
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "coating_type": coating,
        "result": res
    }


_g = StateGraph(State)

_g.add_node("material_check", evaluate_material)
_g.add_node("thread_analysis", analyze_threading)
_g.add_node("certification", finalize_specification)

_g.add_edge(START, "material_check")
_g.add_edge("material_check", "thread_analysis")
_g.add_edge("thread_analysis", "certification")
_g.add_edge("certification", END)

graph = _g.compile()
