# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101707 — Component (segment 22).

Bespoke graph logic for heavy equipment components. This agent validates
technical specifications, evaluates structural integrity ratings, and
issues operational certificates within the building and construction
machinery domain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101707"
UNISPSC_TITLE = "Component"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for heavy equipment components
    specs: dict[str, Any]
    integrity_rating: float
    certificate_id: str
    is_certified: bool


def extract_component_specs(state: State) -> dict[str, Any]:
    """Extracts and normalizes technical specifications from input."""
    inp = state.get("input") or {}
    raw_specs = inp.get("component_data", {})
    return {
        "log": [f"{UNISPSC_CODE}:extract_component_specs"],
        "specs": raw_specs,
    }


def evaluate_structural_integrity(state: State) -> dict[str, Any]:
    """Simulates an integrity evaluation based on provided specs."""
    specs = state.get("specs") or {}
    # Presence of material type and load capacity determines the rating
    has_material = "material" in specs
    has_load = "load_capacity" in specs
    rating = 0.95 if (has_material and has_load) else 0.45
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_structural_integrity"],
        "integrity_rating": rating,
    }


def issue_component_certificate(state: State) -> dict[str, Any]:
    """Issues a domain certificate if integrity meets the regulatory threshold."""
    rating = state.get("integrity_rating", 0.0)
    certified = rating >= 0.8
    cert_id = f"CERT-22-{UNISPSC_CODE}-77" if certified else "DENIED"

    return {
        "log": [f"{UNISPSC_CODE}:issue_component_certificate"],
        "is_certified": certified,
        "certificate_id": cert_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": certified,
            "certificate": cert_id,
            "integrity": rating,
            "status": "VERIFIED" if certified else "REJECTED"
        },
    }


_g = StateGraph(State)
_g.add_node("extract", extract_component_specs)
_g.add_node("evaluate", evaluate_structural_integrity)
_g.add_node("certify", issue_component_certificate)

_g.add_edge(START, "extract")
_g.add_edge("extract", "evaluate")
_g.add_edge("evaluate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
