# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101701 — Chemical (segment 11).

Bespoke graph logic for chemical substance processing, including safety
verification and composition analysis.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101701"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    sds_verified: bool
    hazard_class: str
    purity_level: float
    batch_reference: str


def validate_safety(state: State) -> dict[str, Any]:
    """Verify Safety Data Sheet and hazard classifications."""
    inp = state.get("input") or {}
    sds_provided = inp.get("sds_provided", False)
    h_class = inp.get("hazard_class", "Non-hazardous")

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "sds_verified": bool(sds_provided),
        "hazard_class": str(h_class),
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyze purity levels and assign batch identification."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.99)
    batch = inp.get("batch_id", "BATCH-DEFAULT")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_level": float(purity),
        "batch_reference": f"CHEM-{batch}",
    }


def finalize_certificate(state: State) -> dict[str, Any]:
    """Generate the final chemical certificate of analysis."""
    analysis = {
        "sds_ok": state.get("sds_verified"),
        "purity": state.get("purity_level"),
        "hazard": state.get("hazard_class"),
        "batch": state.get("batch_reference"),
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": analysis,
            "status": "Certified" if state.get("sds_verified") else "Pending Safety Check",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety", validate_safety)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("finalize_certificate", finalize_certificate)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "analyze_composition")
_g.add_edge("analyze_composition", "finalize_certificate")
_g.add_edge("finalize_certificate", END)

graph = _g.compile()
