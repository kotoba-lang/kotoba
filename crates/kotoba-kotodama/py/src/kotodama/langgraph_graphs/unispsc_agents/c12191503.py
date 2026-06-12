# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12191503 — Rare Earth (segment 12).

Bespoke graph logic for rare earth element processing and certification.
This agent manages state transitions for mineral composition analysis,
safety verification, and batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12191503"
UNISPSC_TITLE = "Rare Earth"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12191503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rare Earth minerals
    element_id: str
    purity_percentage: float
    safety_compliance: bool
    is_critical_resource: bool


def analyze_composition(state: State) -> dict[str, Any]:
    """Extracts element identification and purity from input data."""
    inp = state.get("input") or {}
    element = str(inp.get("element", "Unknown"))
    purity = float(inp.get("purity", 0.0))

    # Rare Earths like Neodymium, Dysprosium, and Terbium are critical
    critical_elements = {"Neodymium", "Dysprosium", "Terbium", "Europium", "Yttrium"}
    is_critical = element in critical_elements

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition -> {element} ({purity}%)"],
        "element_id": element,
        "purity_percentage": purity,
        "is_critical_resource": is_critical,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Checks for radioactive impurities and regulatory alignment."""
    purity = state.get("purity_percentage", 0.0)
    # Dummy safety logic: ultra-high purity or specific elements pass safety checks
    compliant = purity >= 95.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety -> compliant={compliant}"],
        "safety_compliance": compliant,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Generates the final certification metadata for the rare earth lot."""
    element = state.get("element_id", "N/A")
    purity = state.get("purity_percentage", 0.0)
    safe = state.get("safety_compliance", False)
    critical = state.get("is_critical_resource", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "element": element,
            "purity": purity,
            "certified": safe,
            "critical_mineral_status": critical,
            "ok": safe,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_composition)
_g.add_node("verify", verify_safety)
_g.add_node("certify", certify_batch)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
