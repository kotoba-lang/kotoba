# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151500 — Raw Material.

Bespoke graph logic for handling raw material intake and quality verification
within segment 11 (Mineral, Agricultural and Forestry Products).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151500"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151500"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Raw Material
    material_type: str
    purity_level: float
    batch_id: str
    is_hazardous: bool
    inspection_passed: bool


def intake_materials(state: State) -> dict[str, Any]:
    """Validates the arrival of raw materials and assigns a batch identifier."""
    inp = state.get("input") or {}
    m_type = inp.get("type", "unspecified")
    batch = inp.get("batch_id", f"BATCH-{UNISPSC_CODE}-001")

    return {
        "log": [f"{UNISPSC_CODE}:intake_materials"],
        "material_type": m_type,
        "batch_id": batch,
        "is_hazardous": inp.get("hazardous", False)
    }


def quality_assessment(state: State) -> dict[str, Any]:
    """Analyzes the purity and safety profile of the raw material batch."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.95)

    # Simple logic: must be > 90% pure unless otherwise specified
    passed = purity > 0.90

    return {
        "log": [f"{UNISPSC_CODE}:quality_assessment"],
        "purity_level": purity,
        "inspection_passed": passed
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Registers the material in the inventory system and prepares the result."""
    status = "ACCEPTED" if state.get("inspection_passed") else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "status": status,
            "purity": state.get("purity_level"),
            "ok": state.get("inspection_passed", False),
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake_materials)
_g.add_node("assess", quality_assessment)
_g.add_node("finalize", finalize_inventory)

_g.add_edge(START, "intake")
_g.add_edge("intake", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
