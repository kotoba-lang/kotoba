# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10122103 — Mineral (segment 10).

Bespoke graph logic for mineral processing, assay analysis, and inventory archival.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10122103"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10122103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mineral
    extraction_site_id: str
    purity_percentage: float
    composition_verified: bool
    mass_tons: float


def validate_extraction(state: State) -> dict[str, Any]:
    """Validate extraction site and initial mass measurements."""
    inp = state.get("input") or {}
    site = inp.get("site_id", "MINE-ALPHA-7")
    mass = float(inp.get("mass_tons", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_extraction(site={site}, mass={mass})"],
        "extraction_site_id": site,
        "mass_tons": mass,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Perform purity analysis and verify mineral composition."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 92.5))
    # In a real scenario, this might involve checking against standard mineral profiles
    is_verified = purity > 0.0 and state.get("mass_tons", 0) > 0
    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition(purity={purity}%)"],
        "purity_percentage": purity,
        "composition_verified": is_verified,
    }


def archive_mineral_lot(state: State) -> dict[str, Any]:
    """Finalize the record for the mineral lot and emit result."""
    verified = state.get("composition_verified", False)
    site = state.get("extraction_site_id", "unknown")
    mass = state.get("mass_tons", 0.0)
    purity = state.get("purity_percentage", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:archive_mineral_lot"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "site_id": site,
                "purity": purity,
                "mass": mass,
                "verified": verified,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_extraction)
_g.add_node("analyze", analyze_composition)
_g.add_node("archive", archive_mineral_lot)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "archive")
_g.add_edge("archive", END)

graph = _g.compile()
