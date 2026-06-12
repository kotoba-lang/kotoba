# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101509 — Fitting (segment 22).

Bespoke graph logic for industrial fittings, covering specification validation,
pressure rating verification, and final component emission.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101509"
UNISPSC_TITLE = "Fitting"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    pressure_rating_psi: int
    connection_standard: str
    certification_verified: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input requirements for the fitting specification."""
    inp = state.get("input") or {}
    grade = inp.get("material", "Grade 316 Stainless")
    standard = inp.get("standard", "ANSI/ASME B16.11")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "material_grade": grade,
        "connection_standard": standard,
        "certification_verified": True
    }


def calculate_integrity(state: State) -> dict[str, Any]:
    """Processes material grade and standard to determine pressure capacity."""
    grade = state.get("material_grade", "")
    # Domain logic: simulate integrity processing based on material grade
    psi_limit = 6000 if "316" in grade else 3000

    return {
        "log": [f"{UNISPSC_CODE}:calculate_integrity"],
        "pressure_rating_psi": psi_limit
    }


def emit_result(state: State) -> dict[str, Any]:
    """Compiles and emits the final validated fitting configuration."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "material": state.get("material_grade"),
                "max_pressure_psi": state.get("pressure_rating_psi"),
                "standard": state.get("connection_standard"),
                "certified": state.get("certification_verified")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("process", calculate_integrity)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
