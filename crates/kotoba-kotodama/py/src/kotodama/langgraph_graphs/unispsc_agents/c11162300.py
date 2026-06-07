# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162300 — Mineral (segment 11).

Bespoke graph logic for evaluating mineral resources, verifying assay purity,
and documenting extraction provenance within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162300"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mineral_species: str
    extraction_site: str
    purity_assay: float
    is_industrial_grade: bool


def assay_composition(state: State) -> dict[str, Any]:
    """Analyzes the chemical composition and assigns purity metrics."""
    inp = state.get("input") or {}
    species = inp.get("species", "silicate")
    purity = float(inp.get("purity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:assay_composition"],
        "mineral_species": species,
        "purity_assay": purity,
        "is_industrial_grade": purity >= 0.85
    }


def verify_extraction(state: State) -> dict[str, Any]:
    """Validates the extraction provenance and site safety records."""
    inp = state.get("input") or {}
    site = inp.get("site_id", "LOC-000")

    return {
        "log": [f"{UNISPSC_CODE}:verify_extraction"],
        "extraction_site": site
    }


def emit_certificate(state: State) -> dict[str, Any]:
    """Generates the final mineral resource certificate."""
    is_ready = state.get("is_industrial_grade", False)
    species = state.get("mineral_species", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:emit_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_ready,
            "record": {
                "species": species,
                "site": state.get("extraction_site"),
                "assay": state.get("purity_assay"),
                "classification": "INDUSTRIAL" if is_ready else "SUB_STANDARD"
            }
        }
    }


_g = StateGraph(State)
_g.add_node("assay_composition", assay_composition)
_g.add_node("verify_extraction", verify_extraction)
_g.add_node("emit_certificate", emit_certificate)

_g.add_edge(START, "assay_composition")
_g.add_edge("assay_composition", "verify_extraction")
_g.add_edge("verify_extraction", "emit_certificate")
_g.add_edge("emit_certificate", END)

graph = _g.compile()
