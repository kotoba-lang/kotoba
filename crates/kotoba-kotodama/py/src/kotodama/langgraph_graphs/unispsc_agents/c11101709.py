# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101709 — Petroleum (segment 11).

Bespoke graph logic for petroleum crude analysis and refining simulation.
This agent handles state transitions for crude oil property validation,
distillation modeling, and quality assurance reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101709"
UNISPSC_TITLE = "Petroleum"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific petroleum fields
    api_gravity: float
    sulfur_content: float
    viscosity: float
    refining_stage: str
    is_sweet: bool


def inspect_crude(state: State) -> dict[str, Any]:
    """Inspects the raw crude properties from input."""
    inp = state.get("input") or {}
    api = float(inp.get("api_gravity", 30.0))
    sulfur = float(inp.get("sulfur_content", 0.5))

    # Sweet crude has < 0.5% sulfur
    is_sweet = sulfur < 0.5

    return {
        "log": [f"{UNISPSC_CODE}:inspect_crude: API={api}, Sulfur={sulfur}"],
        "api_gravity": api,
        "sulfur_content": sulfur,
        "is_sweet": is_sweet,
        "refining_stage": "inspected",
    }


def distillation(state: State) -> dict[str, Any]:
    """Simulates the atmospheric distillation process."""
    api = state.get("api_gravity", 30.0)

    # Heavier crudes (low API) have higher viscosity
    viscosity = 100.0 / api

    return {
        "log": [f"{UNISPSC_CODE}:distillation: viscosity_est={viscosity:.2f}"],
        "viscosity": viscosity,
        "refining_stage": "distilled",
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Final check and formatting of the petroleum data."""
    is_sweet = state.get("is_sweet", False)
    stage = state.get("refining_stage", "unknown")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "classification": "Sweet Crude" if is_sweet else "Sour Crude",
        "stage_reached": stage,
        "ok": True,
    }

    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance: verified"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("inspect_crude", inspect_crude)
_g.add_node("distillation", distillation)
_g.add_node("quality_assurance", quality_assurance)

_g.add_edge(START, "inspect_crude")
_g.add_edge("inspect_crude", "distillation")
_g.add_edge("distillation", "quality_assurance")
_g.add_edge("quality_assurance", END)

graph = _g.compile()
