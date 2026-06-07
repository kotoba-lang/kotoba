# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111700 — Naval (segment 25).

This agent provides bespoke logic for naval vessel assessment, evaluating
seaworthiness and deployment readiness for specialized marine assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111700"
UNISPSC_TITLE = "Naval"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Naval assets
    vessel_class: str
    hull_id: str
    tonnage: int
    readiness_level: float
    is_seaworthy: bool


def inspect_vessel_hull(state: State) -> dict[str, Any]:
    """Inspects the naval vessel hull and registers primary identifiers."""
    inp = state.get("input") or {}
    vclass = inp.get("class", "Destroyer")
    hid = inp.get("hull_id", "DDG-1000")
    tns = inp.get("tonnage", 15000)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel_hull -> Registered {hid}"],
        "vessel_class": vclass,
        "hull_id": hid,
        "tonnage": tns,
    }


def evaluate_readiness(state: State) -> dict[str, Any]:
    """Calculates the deployment readiness based on vessel specifications."""
    tonnage = state.get("tonnage", 0)
    vclass = state.get("vessel_class", "")

    # Simple logic to determine readiness level
    base_readiness = 0.9 if vclass == "Carrier" else 0.8
    if tonnage > 20000:
        base_readiness -= 0.05

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_readiness -> Score {base_readiness}"],
        "readiness_level": base_readiness,
        "is_seaworthy": base_readiness > 0.75,
    }


def certify_vessel(state: State) -> dict[str, Any]:
    """Finalizes the naval certification and emits the result payload."""
    seaworthy = state.get("is_seaworthy", False)
    level = state.get("readiness_level", 0.0)
    hid = state.get("hull_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:certify_vessel -> {'Certified' if seaworthy else 'Denied'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "hull_id": hid,
            "readiness_score": level,
            "certified": seaworthy,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_vessel_hull", inspect_vessel_hull)
_g.add_node("evaluate_readiness", evaluate_readiness)
_g.add_node("certify_vessel", certify_vessel)

_g.add_edge(START, "inspect_vessel_hull")
_g.add_edge("inspect_vessel_hull", "evaluate_readiness")
_g.add_edge("evaluate_readiness", "certify_vessel")
_g.add_edge("certify_vessel", END)

graph = _g.compile()
