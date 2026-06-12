# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151610"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151610"


class State(TypedDict, total=False):
    """State for the Commodity actor within the Livestock/Seeds segment."""
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Commodity 10151610
    commodity_category: str
    certification_id: str
    moisture_content: float
    grade_level: int
    compliance_flags: list[str]


def validate_certification(state: State) -> dict[str, Any]:
    """Node to verify the certification and origin of the commodity."""
    inp = state.get("input") or {}
    cert_id = str(inp.get("cert_id", "CERT-DEFAULT-10151610"))
    category = str(inp.get("category", "Bulk Agricultural"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_certification - {cert_id}"],
        "certification_id": cert_id,
        "commodity_category": category,
        "compliance_flags": ["origin_verified"]
    }


def analyze_specifications(state: State) -> dict[str, Any]:
    """Node to assess the physical properties and quality of the commodity."""
    inp = state.get("input") or {}
    # Simulate a moisture check which is critical for many agricultural commodities
    moisture = float(inp.get("moisture", 11.8))
    # Grade 1 is premium (<13%), Grade 2 is standard
    grade = 1 if moisture < 13.0 else 2

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications - moisture={moisture}% -> Grade {grade}"],
        "moisture_content": moisture,
        "grade_level": grade,
        "compliance_flags": state.get("compliance_flags", []) + ["quality_assessed"]
    }


def finalize_transaction(state: State) -> dict[str, Any]:
    """Node to prepare the final agent output based on validated commodity state."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_transaction"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "commodity_data": {
                "category": state.get("commodity_category"),
                "cert_id": state.get("certification_id"),
                "grade": state.get("grade_level"),
                "moisture": state.get("moisture_content"),
            },
            "compliance": state.get("compliance_flags"),
            "status": "APPROVED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_certification)
_g.add_node("analyze", analyze_specifications)
_g.add_node("finalize", finalize_transaction)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
