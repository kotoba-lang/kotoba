# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101618 — Mineral (segment 11).

Bespoke graph logic for mineral resource validation, assay processing, and
certification. This agent manages state transitions for raw mineral extraction
metadata within the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101618"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101618"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Mineral
    extraction_site_id: str
    purity_grade: float
    mineral_category: str  # e.g., Metallic, Non-metallic, Rare Earth
    assay_verified: bool


def inspect_sample(state: State) -> dict[str, Any]:
    """Inspects the incoming mineral sample metadata and determines category."""
    inp = state.get("input") or {}
    site = inp.get("site_id", "UNKNOWN-SITE")
    category = inp.get("category", "Non-metallic")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_sample - site: {site}"],
        "extraction_site_id": site,
        "mineral_category": category,
    }


def assay_purity(state: State) -> dict[str, Any]:
    """Simulates an assay process to verify mineral purity levels."""
    inp = state.get("input") or {}
    # Simulate assay logic: higher mass usually leads to more rigorous testing
    raw_purity = inp.get("declared_purity", 0.85)
    verified = raw_purity > 0.90

    return {
        "log": [f"{UNISPSC_CODE}:assay_purity - verified: {verified}"],
        "purity_grade": raw_purity,
        "assay_verified": verified,
    }


def certify_mineral(state: State) -> dict[str, Any]:
    """Issues a digital certificate for the mineral sample based on assay results."""
    is_verified = state.get("assay_verified", False)
    purity = state.get("purity_grade", 0.0)
    category = state.get("mineral_category", "Unknown")

    cert_status = "CERTIFIED" if is_verified else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_mineral - status: {cert_status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verification": {
                "status": cert_status,
                "purity": purity,
                "category": category,
                "site": state.get("extraction_site_id"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_sample)
_g.add_node("assay", assay_purity)
_g.add_node("certify", certify_mineral)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "assay")
_g.add_edge("assay", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
