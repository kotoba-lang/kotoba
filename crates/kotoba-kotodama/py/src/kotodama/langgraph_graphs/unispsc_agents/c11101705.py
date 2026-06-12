# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101705 — Metal (segment 11).

Bespoke graph logic for metal material processing, validation, and certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101705"
UNISPSC_TITLE = "Metal"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Metal
    alloy_composition: dict[str, float]
    hardness_vickers: float
    batch_id: str
    purity_certified: bool


def analyze_spec(state: State) -> dict[str, Any]:
    """Inspects the input specification for metal properties and batch IDs."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", {"Fe": 99.0, "C": 1.0})
    batch = inp.get("batch_id", "MB-DEFAULT")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_spec"],
        "alloy_composition": alloy,
        "batch_id": batch,
    }


def verify_properties(state: State) -> dict[str, Any]:
    """Simulates verification of hardness and purity for the specific metal batch."""
    alloy = state.get("alloy_composition", {})
    # Mock calculation: higher carbon content increases simulated Vickers hardness
    carbon_pct = alloy.get("C", 0.0)
    simulated_hardness = 100.0 + (carbon_pct * 50.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_properties"],
        "hardness_vickers": simulated_hardness,
        "purity_certified": bool(alloy),
    }


def certify_output(state: State) -> dict[str, Any]:
    """Generates the final certification result for the metal material."""
    batch = state.get("batch_id", "UNKNOWN")
    hardness = state.get("hardness_vickers", 0.0)
    certified = state.get("purity_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "batch_id": batch,
            "vickers_hardness": hardness,
            "certified": certified,
            "did": UNISPSC_DID,
            "status": "APPROVED" if certified else "PENDING",
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_spec", analyze_spec)
_g.add_node("verify_properties", verify_properties)
_g.add_node("certify_output", certify_output)

_g.add_edge(START, "analyze_spec")
_g.add_edge("analyze_spec", "verify_properties")
_g.add_edge("verify_properties", "certify_output")
_g.add_edge("certify_output", END)

graph = _g.compile()
