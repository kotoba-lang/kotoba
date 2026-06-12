# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11171901 — Sheep skins (segment 11).
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11171901"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11171901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    batch_id: str
    skin_grade: str
    moisture_level: float
    tanning_requirement: str
    quarantine_cleared: bool


def validate_batch(state: State) -> dict[str, Any]:
    """Validates the incoming sheep skin batch metadata and source info."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "SB-DEFAULT")
    source_verified = "source" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_batch"],
        "batch_id": batch_id,
        "quarantine_cleared": source_verified,
    }


def analyze_quality(state: State) -> dict[str, Any]:
    """Analyzes the physical properties of the skins for grading."""
    inp = state.get("input") or {}
    weight = inp.get("average_weight", 0.0)
    moisture = inp.get("moisture_content", 12.0)

    # Grading logic based on hypothetical sheep skin standards
    grade = "Premium" if weight > 4.5 and moisture < 15.0 else "Standard"
    tanning = "Vegetable" if grade == "Premium" else "Mineral"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_quality"],
        "skin_grade": grade,
        "moisture_level": moisture,
        "tanning_requirement": tanning,
    }


def record_inventory(state: State) -> dict[str, Any]:
    """Finalizes the ledger entry for the processed skin batch."""
    return {
        "log": [f"{UNISPSC_CODE}:record_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "grade": state.get("skin_grade"),
            "process": state.get("tanning_requirement"),
            "status": "archived" if state.get("quarantine_cleared") else "held",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_batch)
_g.add_node("analyze", analyze_quality)
_g.add_node("emit", record_inventory)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
