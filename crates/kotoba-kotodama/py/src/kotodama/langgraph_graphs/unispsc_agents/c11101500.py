# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101500 — Material (segment 11).

Bespoke graph logic for screening biological and animal-derived materials,
assigning biosecurity classifications, and emitting compliance manifests.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101500"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for biological materials
    origin_source: str
    biosecurity_level: int
    is_hazardous: bool
    inspection_passed: bool


def screen_material(state: State) -> dict[str, Any]:
    """Screens the material for origin data and hazard indicators."""
    inp = state.get("input") or {}
    source = inp.get("source", "unspecified")
    hazard = inp.get("hazard_detected", False)

    return {
        "log": [f"{UNISPSC_CODE}:screen_material"],
        "origin_source": source,
        "is_hazardous": hazard,
        "inspection_passed": bool(source != "unspecified"),
    }


def classify_bio_safety(state: State) -> dict[str, Any]:
    """Assigns a biosecurity level based on origin and hazard status."""
    is_haz = state.get("is_hazardous", False)
    source = state.get("origin_source", "")

    # Simple logic to determine BSL (Biosecurity Level)
    bsl = 1
    if is_haz:
        bsl = 3
    elif source and "restricted" in source.lower():
        bsl = 2

    return {
        "log": [f"{UNISPSC_CODE}:classify_bio_safety"],
        "biosecurity_level": bsl,
    }


def emit_material_manifest(state: State) -> dict[str, Any]:
    """Compiles the final state into a compliant material manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_material_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "origin": state.get("origin_source"),
                "bsl_rating": state.get("biosecurity_level"),
                "hazard_status": "HIGH" if state.get("is_hazardous") else "NORMAL",
                "verified": state.get("inspection_passed"),
            },
            "ok": state.get("inspection_passed", False),
        },
    }


_g = StateGraph(State)

_g.add_node("screen_material", screen_material)
_g.add_node("classify_bio_safety", classify_bio_safety)
_g.add_node("emit_material_manifest", emit_material_manifest)

_g.add_edge(START, "screen_material")
_g.add_edge("screen_material", "classify_bio_safety")
_g.add_edge("classify_bio_safety", "emit_material_manifest")
_g.add_edge("emit_material_manifest", END)

graph = _g.compile()
