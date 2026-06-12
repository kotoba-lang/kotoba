# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102002 — Fastener (segment 20).

Bespoke LangGraph implementation for managing fastener specifications,
mechanical properties analysis, and technical batch record finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102002"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Fastener
    material_grade: str
    tensile_strength_psi: int
    thread_specification: str
    quality_control_passed: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the fastener input."""
    inp = state.get("input") or {}
    thread = inp.get("thread", "Standard UNC")
    material = inp.get("material", "Carbon Steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications -> {thread} ({material})"],
        "thread_specification": thread,
        "material_grade": material,
    }


def analyze_mechanical_properties(state: State) -> dict[str, Any]:
    """Determines tensile strength based on material grade."""
    material = state.get("material_grade", "Unknown")

    # Logic simulating mechanical analysis
    strengths = {
        "Carbon Steel": 60000,
        "Grade 5": 120000,
        "Grade 8": 150000,
        "Stainless 316": 75000,
    }
    strength = strengths.get(material, 50000)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_mechanical_properties -> {strength} PSI"],
        "tensile_strength_psi": strength,
        "quality_control_passed": strength >= 60000,
    }


def finalize_batch_record(state: State) -> dict[str, Any]:
    """Generates the final technical data sheet for the fastener."""
    is_ok = state.get("quality_control_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "thread": state.get("thread_specification"),
                "material": state.get("material_grade"),
                "tensile_strength": state.get("tensile_strength_psi"),
            },
            "status": "APPROVED" if is_ok else "REJECTED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("analyze_mechanical_properties", analyze_mechanical_properties)
_g.add_node("finalize_batch_record", finalize_batch_record)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "analyze_mechanical_properties")
_g.add_edge("analyze_mechanical_properties", "finalize_batch_record")
_g.add_edge("finalize_batch_record", END)

graph = _g.compile()
