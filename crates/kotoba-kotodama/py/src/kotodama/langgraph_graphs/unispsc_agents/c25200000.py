# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25200000 — Aerospace (segment 25).

Bespoke graph logic for aerospace component certification and airworthiness
verification. This agent manages the lifecycle of aerospace assets from
initial inspection through to compliance certification and final recording.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25200000"
UNISPSC_TITLE = "Aerospace"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25200000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Aerospace domain state
    certification_level: str
    airworthiness_checked: bool
    component_integrity_score: float
    maintenance_interval_hours: int


def inspect_component(state: State) -> dict[str, Any]:
    """Inspects the aerospace component for structural integrity."""
    inp = state.get("input") or {}
    # Simulate an integrity check from input or default to high quality
    integrity = float(inp.get("integrity", 0.95))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_component"],
        "component_integrity_score": integrity,
        "airworthiness_checked": integrity > 0.85,
    }


def certify_compliance(state: State) -> dict[str, Any]:
    """Assigns a certification level based on the integrity score."""
    integrity = state.get("component_integrity_score", 0.0)

    if integrity > 0.98:
        level = "Premium"
    elif integrity > 0.90:
        level = "Standard"
    else:
        level = "Restricted"

    return {
        "log": [f"{UNISPSC_CODE}:certify_compliance"],
        "certification_level": level,
        "maintenance_interval_hours": 500 if level == "Restricted" else 2000,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Finalizes the aerospace certification record."""
    airworthy = state.get("airworthiness_checked", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": state.get("certification_level"),
            "airworthy": airworthy,
            "next_maintenance_h": state.get("maintenance_interval_hours"),
            "ok": airworthy,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_component)
_g.add_node("certify", certify_compliance)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "certify")
_g.add_edge("certify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
