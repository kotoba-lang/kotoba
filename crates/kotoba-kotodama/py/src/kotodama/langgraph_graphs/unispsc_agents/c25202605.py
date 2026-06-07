# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202605 — Aircraft Parts (segment 25).

Bespoke graph logic for managing aircraft part inventory and airworthiness
verification. This agent handles documentation inspection, airworthiness
validation, and release processing for aerospace components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202605"
UNISPSC_TITLE = "Aircraft Parts"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Aircraft Parts domain
    part_number: str
    certification_authority: str
    airworthiness_status: str
    maintenance_release_found: bool


def inspect_documentation(state: State) -> dict[str, Any]:
    """Node to verify the presence of mandatory maintenance documentation."""
    inp = state.get("input") or {}
    pn = inp.get("part_number", "UNKNOWN-PART")
    auth = inp.get("certification_authority", "FAA")

    # Simulate checking for an 8130-3 or EASA Form 1
    has_release = "release_form" in inp or inp.get("certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_documentation: {pn}"],
        "part_number": pn,
        "certification_authority": auth,
        "maintenance_release_found": has_release
    }


def verify_airworthiness(state: State) -> dict[str, Any]:
    """Node to evaluate the airworthiness status based on documentation and history."""
    has_release = state.get("maintenance_release_found", False)

    # In a real scenario, this would check shelf life, AD compliance, etc.
    status = "AIRWORTHY" if has_release else "UNSERVICEABLE"

    return {
        "log": [f"{UNISPSC_CODE}:verify_airworthiness: result={status}"],
        "airworthiness_status": status
    }


def finalize_release(state: State) -> dict[str, Any]:
    """Node to compile the final response and inventory status for the actor."""
    pn = state.get("part_number")
    status = state.get("airworthiness_status")
    auth = state.get("certification_authority")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_release"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "part_number": pn,
            "certification": auth,
            "airworthiness_status": status,
            "ok": status == "AIRWORTHY",
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_documentation", inspect_documentation)
_g.add_node("verify_airworthiness", verify_airworthiness)
_g.add_node("finalize_release", finalize_release)

_g.add_edge(START, "inspect_documentation")
_g.add_edge("inspect_documentation", "verify_airworthiness")
_g.add_edge("verify_airworthiness", "finalize_release")
_g.add_edge("finalize_release", END)

graph = _g.compile()
