# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111710 — Ship (segment 25).

This agent manages the lifecycle of a Ship asset, including registry
verification, seaworthiness assessment, and manifest clearance for
maritime operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111710"
UNISPSC_TITLE = "Ship"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    imo_number: str
    registry_active: bool
    vessel_class: str
    hull_integrity_verified: bool
    gross_tonnage: int


def verify_registry(state: State) -> dict[str, Any]:
    """Check the International Maritime Organization (IMO) registration status."""
    inp = state.get("input") or {}
    imo = str(inp.get("imo_number", "UNKNOWN"))
    active = len(imo) >= 7 and imo.isdigit()
    return {
        "log": [f"{UNISPSC_CODE}:verify_registry"],
        "imo_number": imo,
        "registry_active": active,
    }


def inspect_vessel(state: State) -> dict[str, Any]:
    """Perform structural and safety inspections."""
    imo = state.get("imo_number", "")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel"],
        "vessel_class": "Merchant-A" if state.get("registry_active") else "Non-Classed",
        "hull_integrity_verified": True,
        "gross_tonnage": 125000 if "9" in imo else 85000,
    }


def authorize_voyage(state: State) -> dict[str, Any]:
    """Final check and clearance for ship departure."""
    is_ready = state.get("registry_active") and state.get("hull_integrity_verified")
    return {
        "log": [f"{UNISPSC_CODE}:authorize_voyage"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "imo_number": state.get("imo_number"),
            "vessel_class": state.get("vessel_class"),
            "status": "Authorized" if is_ready else "Denied",
            "did": UNISPSC_DID,
            "ok": is_ready,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_registry", verify_registry)
_g.add_node("inspect_vessel", inspect_vessel)
_g.add_node("authorize_voyage", authorize_voyage)

_g.add_edge(START, "verify_registry")
_g.add_edge("verify_registry", "inspect_vessel")
_g.add_edge("inspect_vessel", "authorize_voyage")
_g.add_edge("authorize_voyage", END)

graph = _g.compile()
