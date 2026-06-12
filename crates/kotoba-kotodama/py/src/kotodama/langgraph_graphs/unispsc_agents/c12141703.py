# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141703 — Material (segment 12).
Specialized for biological material, feed, or bedding in agricultural contexts.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141703"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141703"


class State(TypedDict, total=False):
    """Domain state for Material (UNISPSC 12141703)."""
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields
    material_grade: str
    batch_identifier: str
    purity_level: float
    safety_certification: bool
    storage_conditions: str


def inspect_manifest(state: State) -> dict[str, Any]:
    """Validates the incoming material manifest and assigns a batch tracking ID."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", f"BATCH-{UNISPSC_CODE}-DEFAULT")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_manifest"],
        "batch_identifier": batch_id,
        "material_grade": inp.get("requested_grade", "Standard"),
    }


def analyze_properties(state: State) -> dict[str, Any]:
    """Simulates property analysis including purity and safety checks."""
    # Simulation logic based on grade
    grade = state.get("material_grade", "Standard")
    purity = 0.98 if grade == "Premium" else 0.92

    return {
        "log": [f"{UNISPSC_CODE}:analyze_properties"],
        "purity_level": purity,
        "safety_certification": True,
        "storage_conditions": "Keep dry and ventilated",
    }


def finalize_inventory_record(state: State) -> dict[str, Any]:
    """Packages the final material audit into the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "batch": state.get("batch_identifier"),
                "grade": state.get("material_grade"),
                "purity": state.get("purity_level"),
                "certified": state.get("safety_certification"),
                "storage": state.get("storage_conditions"),
            },
            "status": "Verified",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_manifest", inspect_manifest)
_g.add_node("analyze_properties", analyze_properties)
_g.add_node("finalize_inventory_record", finalize_inventory_record)

_g.add_edge(START, "inspect_manifest")
_g.add_edge("inspect_manifest", "analyze_properties")
_g.add_edge("analyze_properties", "finalize_inventory_record")
_g.add_edge("finalize_inventory_record", END)

graph = _g.compile()
