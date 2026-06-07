# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12142003 — Cerium (segment 12).

This bespoke implementation handles the state transitions for processing
Cerium, a rare earth element used in glass polishing and catalysts.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142003"
UNISPSC_TITLE = "Cerium"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Cerium (Rare Earth Metal)
    oxide_state: str        # e.g., CeO2, Ce2O3
    purity_pct: float       # Percentage of purity
    refinement_batch: str   # Unique identifier for the refinement run
    safety_cleared: bool    # Verification of non-radioactive threshold


def initialize_batch(state: State) -> dict[str, Any]:
    """Initializes the Cerium refinement batch and safety parameters."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "CE-RAW-001")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_batch:{batch_id}"],
        "refinement_batch": batch_id,
        "purity_pct": 88.5,
        "safety_cleared": False,
    }


def purify_element(state: State) -> dict[str, Any]:
    """Simulates the chemical purification of Cerium using ion exchange."""
    current_purity = state.get("purity_pct", 0.0)
    # Simulate purification logic by increasing purity grade
    new_purity = min(99.99, current_purity + 11.45)
    return {
        "log": [f"{UNISPSC_CODE}:purify_element:target_purity_reached"],
        "purity_pct": new_purity,
        "oxide_state": "CeO2",
        "safety_cleared": True,
    }


def package_and_seal(state: State) -> dict[str, Any]:
    """Finalizes the batch for industrial glass polishing or catalyst use."""
    purity = state.get("purity_pct", 0.0)
    batch = state.get("refinement_batch", "N/A")
    is_safe = state.get("safety_cleared", False)

    return {
        "log": [f"{UNISPSC_CODE}:package_and_seal"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_metadata": {
                "id": batch,
                "purity": f"{purity}%",
                "oxide_form": state.get("oxide_state"),
                "safe": is_safe
            },
            "ok": purity >= 99.9 and is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_batch", initialize_batch)
_g.add_node("purify_element", purify_element)
_g.add_node("package_and_seal", package_and_seal)

_g.add_edge(START, "initialize_batch")
_g.add_edge("initialize_batch", "purify_element")
_g.add_edge("purify_element", "package_and_seal")
_g.add_edge("package_and_seal", END)

graph = _g.compile()
