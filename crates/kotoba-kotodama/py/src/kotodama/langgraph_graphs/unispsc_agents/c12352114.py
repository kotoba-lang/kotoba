# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352114 — Chemical (segment 12).
Bespoke logic for chemical compound validation and safety manifest generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352114"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352114"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Chemical"
    sds_verified: bool
    hazard_class: str
    purity_percentage: float
    storage_conditions: str
    batch_tracking_id: str


def validate_safety_compliance(state: State) -> dict[str, Any]:
    """Ensures Safety Data Sheet (SDS) presence and classifies hazards."""
    inp = state.get("input") or {}
    sds_id = inp.get("sds_id")
    h_class = inp.get("hazard_code", "NON-HAZARDOUS")

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_compliance"],
        "sds_verified": sds_id is not None,
        "hazard_class": h_class,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes chemical purity and storage requirements."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 99.0))
    storage = inp.get("storage", "Room Temp")
    batch_id = f"CHM-{UNISPSC_CODE}-{inp.get('lot', 'DEFAULT')}"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_percentage": purity,
        "storage_conditions": storage,
        "batch_tracking_id": batch_id,
    }


def emit_chemical_manifest(state: State) -> dict[str, Any]:
    """Finalizes the chemical data manifest for the ledger."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_chemical_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "compliance": {
                "sds": state.get("sds_verified"),
                "hazard_class": state.get("hazard_class"),
            },
            "specs": {
                "purity": state.get("purity_percentage"),
                "storage": state.get("storage_conditions"),
                "batch_id": state.get("batch_tracking_id"),
            },
            "ok": state.get("sds_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_safety_compliance)
_g.add_node("analyze", analyze_composition)
_g.add_node("emit", emit_chemical_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
