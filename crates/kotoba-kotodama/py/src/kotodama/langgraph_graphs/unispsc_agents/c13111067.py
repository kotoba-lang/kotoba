# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111067 — Mineral Extraction.
Bespoke implementation for site surveying, mineral extraction, and reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111067"
UNISPSC_TITLE = "Mineral Extraction"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111067"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mineral Extraction
    site_id: str
    mineral_type: str
    volume_tonnes: float
    safety_check_passed: bool


def survey_site(state: State) -> dict[str, Any]:
    """Assess the extraction site and confirm safety parameters."""
    inp = state.get("input") or {}
    site = inp.get("site_id", "SITE-ALPHA-01")
    m_type = inp.get("mineral_type", "Iron Ore")

    # Logic to simulate site verification
    return {
        "log": [f"{UNISPSC_CODE}:survey_site"],
        "site_id": site,
        "mineral_type": m_type,
        "safety_check_passed": True
    }


def execute_extraction(state: State) -> dict[str, Any]:
    """Perform the physical extraction logic and log production volume."""
    inp = state.get("input") or {}
    requested_volume = float(inp.get("requested_volume", 500.0))

    # Simulate extraction yield based on safety clearance
    actual_volume = requested_volume * 0.985 if state.get("safety_check_passed") else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_extraction"],
        "volume_tonnes": actual_volume
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Compile the final extraction statistics and metadata."""
    is_ok = state.get("safety_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "extraction_data": {
                "site_id": state.get("site_id"),
                "mineral": state.get("mineral_type"),
                "extracted_tonnes": state.get("volume_tonnes"),
                "status": "OPERATIONAL_SUCCESS" if is_ok else "SAFETY_HALT",
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("survey_site", survey_site)
_g.add_node("execute_extraction", execute_extraction)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "survey_site")
_g.add_edge("survey_site", "execute_extraction")
_g.add_edge("execute_extraction", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
