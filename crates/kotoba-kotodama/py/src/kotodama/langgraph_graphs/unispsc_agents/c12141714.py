# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141714 — Resin Procurement (segment 12).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141714"
UNISPSC_TITLE = "Resin Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141714"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    resin_type: str
    viscosity_target: float
    is_hazardous: bool
    supplier_rating: int
    procurement_batch_id: str


def validate_specification(state: State) -> dict[str, Any]:
    """Evaluates the technical specifications of the resin procurement request."""
    inp = state.get("input") or {}
    r_type = str(inp.get("resin_type", "industrial-grade"))
    visc = float(inp.get("viscosity", 2500.0))
    # Certain resins trigger specialized handling protocols
    haz = any(x in r_type.lower() for x in ["epoxy", "phenolic", "isocyanate"])

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification:type={r_type}"],
        "resin_type": r_type,
        "viscosity_target": visc,
        "is_hazardous": haz,
    }


def analyze_sourcing(state: State) -> dict[str, Any]:
    """Simulates supplier selection and vetting for the specific resin batch."""
    haz = state.get("is_hazardous", False)
    # Higher rating threshold for hazardous materials
    rating = 90 if haz else 75
    batch_id = f"RES-{UNISPSC_CODE[-4:]}-{hash(state.get('resin_type', '')) % 10000}"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_sourcing:rating_target={rating}"],
        "supplier_rating": rating,
        "procurement_batch_id": batch_id,
    }


def finalize_transaction(state: State) -> dict[str, Any]:
    """Calculates final logistics requirements and prepares the agent result."""
    batch = state.get("procurement_batch_id", "N/A")
    haz = state.get("is_hazardous", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_transaction:batch={batch}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": batch,
            "compliance_protocol": "SDS-LEVEL-3" if haz else "SDS-LEVEL-1",
            "status": "READY_FOR_PURCHASE",
            "verified": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specification", validate_specification)
_g.add_node("analyze_sourcing", analyze_sourcing)
_g.add_node("finalize_transaction", finalize_transaction)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "analyze_sourcing")
_g.add_edge("analyze_sourcing", "finalize_transaction")
_g.add_edge("finalize_transaction", END)

graph = _g.compile()
