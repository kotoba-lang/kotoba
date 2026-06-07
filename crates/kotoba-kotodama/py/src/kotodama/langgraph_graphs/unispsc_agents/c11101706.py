# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101706 — Chemical (segment 11).

Bespoke graph for handling chemical metadata, hazard classification,
and purity validation for the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101706"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Chemical domain
    hazard_class: str
    purity_pct: float
    sds_id: str
    storage_category: str


def validate_hazard_classification(state: State) -> dict[str, Any]:
    """Inspects safety data and checks for hazardous material flags."""
    inp = state.get("input") or {}
    h_class = str(inp.get("hazard_class", "STABLE"))
    sds = str(inp.get("sds_id", "UNDEFINED"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_hazard_classification"],
        "hazard_class": h_class,
        "sds_id": sds,
    }


def analyze_chemical_purity(state: State) -> dict[str, Any]:
    """Assesses the purity level and determines appropriate storage needs."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    h_class = state.get("hazard_class", "STABLE")

    # Logic: High purity or high hazard requires specialized storage category
    if purity > 99.5 or h_class in ["OXIDIZER", "TOXIC", "RADIOACTIVE"]:
        category = "CONTROLLED_ATMOSPHERE"
    else:
        category = "AMBIENT_STORAGE"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_chemical_purity"],
        "purity_pct": purity,
        "storage_category": category,
    }


def compile_chemical_result(state: State) -> dict[str, Any]:
    """Constructs the final verified chemical record and compliance status."""
    is_valid = state.get("sds_id") != "UNDEFINED" and state.get("purity_pct", 0.0) >= 90.0

    return {
        "log": [f"{UNISPSC_CODE}:compile_chemical_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "chemical_attributes": {
                "purity": state.get("purity_pct"),
                "hazard": state.get("hazard_class"),
                "storage": state.get("storage_category"),
            },
            "status": "APPROVED" if is_valid else "PENDING_VERIFICATION",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_hazard_classification", validate_hazard_classification)
_g.add_node("analyze_chemical_purity", analyze_chemical_purity)
_g.add_node("compile_chemical_result", compile_chemical_result)

_g.add_edge(START, "validate_hazard_classification")
_g.add_edge("validate_hazard_classification", "analyze_chemical_purity")
_g.add_edge("analyze_chemical_purity", "compile_chemical_result")
_g.add_edge("compile_chemical_result", END)

graph = _g.compile()
