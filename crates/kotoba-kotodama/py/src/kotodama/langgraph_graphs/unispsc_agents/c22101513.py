# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101513 — Fastener.
Bespoke graph for managing fastener specifications and structural load ratings.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101513"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101513"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Fastener domain state
    material_type: str
    tensile_strength_psi: int
    finish_coating: str
    compliance_verified: bool


def validate_spec(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "material_type": material,
        "finish_coating": inp.get("finish", "Zinc Plated"),
    }


def analyze_performance(state: State) -> dict[str, Any]:
    material = state.get("material_type", "Unknown")
    # Engineering specification mapping
    lookup = {
        "Carbon Steel": 120000,
        "Stainless Steel": 90000,
        "Alloy Steel": 180000,
        "Titanium": 140000,
    }
    strength = lookup.get(material, 50000)
    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "tensile_strength_psi": strength,
        "compliance_verified": strength >= 70000,
    }


def emit_certification(state: State) -> dict[str, Any]:
    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_type"),
                "strength": state.get("tensile_strength_psi"),
                "finish": state.get("finish_coating"),
                "verified": state.get("compliance_verified"),
            },
            "ok": state.get("compliance_verified", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_spec)
_g.add_node("analyze_performance", analyze_performance)
_g.add_node("emit_certification", emit_certification)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "analyze_performance")
_g.add_edge("analyze_performance", "emit_certification")
_g.add_edge("emit_certification", END)

graph = _g.compile()
